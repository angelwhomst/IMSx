from fastapi import APIRouter, Depends, HTTPException, Response
from typing import List
from pydantic import BaseModel
import logging
from fastapi.responses import JSONResponse
import database
from routers.auth import role_required, get_current_active_user


logging.basicConfig(level=logging.INFO)
router = APIRouter()

# Pydantic Models
class CartItemInput(BaseModel):
    productName: str
    category: str
    size: str
    quantity: int
    price: float

class CheckoutRequest(BaseModel):
    cart: List[CartItemInput]

# In-memory cart storage
cart = []

# Add to cart
@router.post("/sales/cart", dependencies=[Depends(role_required(["employee"]))])
async def add_to_cart(item: CartItemInput):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        # retrieve productID based on productName, category, and size
        await cursor.execute(
            """
            SELECT productID, currentStock 
            FROM Products
            WHERE productName = ? AND category = ? AND size = ?
            """,
            (item.productName, item.category, item.size)
        )
        product_row = await cursor.fetchone()

        if not product_row:
            raise HTTPException(
                status_code=404,
                detail=f"Product '{item.productName}' with category '{item.category}' and size '{item.size}' not found."
            )

        productID, currentStock = product_row

        # check if enough stock is available
        if currentStock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for product '{item.productName}'. Available stock: {currentStock}."
            )

        # Add to in-memory cart
        cart_item = {
            "productID": productID,
            "productName": item.productName,
            "category": item.category,
            "size": item.size,
            "quantity": item.quantity,
            "price": item.price
        }
        cart.append(cart_item)

        return {"message": "Item added to cart."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await conn.close()

# view cart
@router.get("/sales/cart", dependencies=[Depends(role_required(["employee"]))])
async def view_cart():
    return cart

# process sales endpoint
@router.post("/sales/checkout")
async def checkout(request: CheckoutRequest, current_user=Depends(get_current_active_user)):
    logging.info(f"Checkout request received: {request}")
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        if not cart:
            raise HTTPException(status_code=400, detail="Cart is empty.")
        
        #generate variantID list from the cart
        variant_id_list = []

        for item in cart:
            # fetch `variantIDs` for each product and size
            await cursor.execute(
                '''select top(?) variantID
                from productVariants
                where productID =?
                and isAvailable = 1''',
                (item['quantity'], item['productID'])
            )
            variants = await cursor.fetchall()

            if len(variants) < item['quantity']:
                raise HTTPException(status_code=400, detail=f"Not enough available variants for product '{item['productName']}' with size '{item['size']}'.")
            
            # add variantIDs to the list
            variant_id_list.extend([variant[0] for variant in variants])
        
        # call the CheckoutSale stored procedure
        variant_id_list_str = ",".join(map(str, variant_id_list))
        await cursor.execute(
            '''exec CheckoutSale @userID = ?, @variantIDList =?''',
            (current_user.userID, variant_id_list_str)
        )
        await conn.commit()
        logging.info("Checkout successful.")

        #clear in-memory cart after successful checkout
        cart.clear()
        return JSONResponse(content={"message": "Checkout successful!"}, status_code=200)   
    
    except HTTPException as http_err:
        # Catch HTTP exceptions explicitly
        logging.error(f"HTTPException occurred: {http_err.detail}")
        raise http_err
    
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await conn.close()

# sales history for employee
@router.get('/sales/history', dependencies=[Depends(role_required(["employee"]))])
async def get_sales_history(current_user=Depends(get_current_active_user)):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        await cursor.execute(
            '''exec EmployeeSalesHistory @userID = ?''',
            current_user.userID
        )
        sales_rows = await cursor.fetchall()

        # constructing teh response
        sales_history = [
            {
                "Product Name": row[0],
                "Category": row[1],
                "Size": row[2], 
                "Total Quantity Sold": row[3],
                "Total Amount": row[4],
                "Sales Date": row[5].strftime("%m-%d-%Y %I:%M %p"),
            }
            for row in sales_rows
        ]

        return{"Employee Sales History": sales_history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        await conn.close()
    
# get products per category for the dropdown in sales logic
@router.get("/sales/products", dependencies=[Depends(role_required(["employee"]))])
async def get_products_per_category(category: str = "All Categories"):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        # call the stored procedure
        await cursor.execute('exec GetProductByCategory @category = ?', (category,))
        products = await cursor.fetchall()
        
        # format the response
        product_list = [
            {
                "productName": row[0],
                "size": row[1],
                "price": f"₱{row[2]:.2f}",
                "category": row[3],
                "image": row[4] if row[4] else "https://via.placeholder.com/150"
            }
            for row in products
        ]

        return {"products": product_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        await conn.close()


# sales history admin side
@router.get('/sales/data', dependencies=[Depends(role_required(["admin"]))])
async def sales_data():
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try: 
        await cursor.execute(
            '''exec SalesData'''
        )
        sales_row = await cursor.fetchall()

        # constructing teh response
        sales_data = [
            {
                "Product Name": row[0],
                "Category": row[1],
                "Size": row[2], 
                "Total Quantity Sold": row[3],
                "Total Amount": row[4],
                "Sales Date": row[5].strftime("%m-%d-%Y %I:%M %p"),
            }
            for row in sales_row
        ]

        return{"Sales History": sales_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()
        
