from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel 
import httpx
from datetime import datetime, date, timedelta
from typing import Optional, List
from decimal import Decimal
import logging
import database
from routers.auth import role_required, get_current_active_user


router = APIRouter(dependencies=[Depends(role_required(["admin"]))])

# base url for vms api
VMS_BASE_URL = 'http://127.0.0.1:8001'

# pydantic model for purchase order
class PurchaseOrder(BaseModel):
    productID: int
    productName: str 
    productDescription: str
    size: str
    color: Optional[str] = 'Black'
    category: str
    quantity: int
    warehouseID: int
    vendorID: int 
    orderDate: Optional[datetime] = None
    expectedDate: Optional[datetime] = None


# function to send purchase order to vms
async def send_order_to_vms(payload: dict):
    async with httpx.AsyncClient() as client:
        try: 
            response = await client.post(f"{VMS_BASE_URL}/vms/orders", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logging.error(f"HTTP error sending order to VMS: {e}")
            raise HTTPException(status_code=500, detail=f"Error sending order to VMS: {e}")
        except ValueError as e:
            logging.error(f"error parsing response from VMS: {e}")
            raise HTTPException(
                status_code=500, detail="Invalied response from VMS")

# webhook to handle stock updates from IMS
@router.post('/stock')
async def stock_webhook(request: Request):
    conn = None
    try:
        #parse payload from ims 
        payload = await request.json()
        logging.info(F"Received payload: {payload}")

        productID = payload.get('productID')
        currentStock = payload.get('currentStock')

        if productID is None or currentStock is None:
            raise HTTPException(status_code=400, detail='Invalid paylaod received')
        
        # check if the stock level requires a PO
        conn = await database.get_db_connection()
        cursor = await conn.cursor()
        await cursor.execute('''SELECT CAST(P.productID AS INT) AS productID,
       P.productName,
       P.productDescription,
       P.size,
       P.color,
       P.category,
       CAST(P.reorderLevel AS INT) AS reorderLevel,
       CAST(P.minStockLevel AS INT) AS minStockLevel,
       CAST(P.warehouseID AS INT) AS warehouseID,
       W.warehouseName
FROM Products P
INNER JOIN Warehouses W ON P.warehouseID = W.warehouseID
WHERE P.productID = ? AND P.isActive = 1;
''',(productID,))
        product = await cursor.fetchone()

        if not product:
            raise HTTPException(status_code=404, detail='Product not found')
        print ('fetched product raw: ', product)
        print("Length of product:", len(product))
        print(f"Type of product: {type(product)}")

        productID = product[0]
        productName = product[1]
        productDescription = product[2]
        size = product[3]
        color = product[4]
        category = product[5]
        reorderLevel = product[6]
        minStockLevel = product[7]
        warehouseID = product[8]
        warehouseName = product[9]

        # extract product details
        (productID, productName, productDescription, size, color, category, 
         reorderLevel, minStockLevel, warehouseID, warehouseName) = (product)

        # if stock is at or below the reorder level, generate PO
        if currentStock <= reorderLevel:
            quantity_to_order = max(minStockLevel - currentStock, 0)
            if quantity_to_order > 0:
                # prepare dynamic dates
                orderDate = datetime.now().date().isoformat()
                expectedDate = (datetime.now() + timedelta(days=7)).date().isoformat()

                # select a vendor for the purchase order
                await cursor.execute('''select top 1 * from Vendors
                                     where isActive = 1
                                     ''')
                vendor = await cursor.fetchone()
                if not vendor:
                    raise HTTPException(status_code=404, detail='No active vendors available.')

                vendorID, vendorName, building, street, barangay, city, country, zipcode = vendor

                # insert into PurchaseOrders table
                await cursor.execute(
                    '''insert into PurchaseOrders (orderDate, orderStatus, statusDate, vendorID)
                    output inserted.orderID
                    values (?, ?, ?, ?)''',
                    (orderDate, 'Pending', datetime.utcnow(), vendorID)
                )
                order = await cursor.fetchone()
                orderID = order[0] if order else None

                if not orderID:
                    raise HTTPException(status_code=500, detail='Failed to create purchase order.')
                
                # insert into PurchaseOrderDetails
                await cursor.execute(
                    '''insert into PurchaseOrderDetails (orderQuantity, expectedDate, warehouseID, orderID)
                    values (?, ?, ?, ?)
                    ''',
                    (quantity_to_order, expectedDate, warehouseID, orderID)
                )
                
                await conn.commit()

                # prepare payload for vms
                po_payload = {
                    "orderID": orderID,
                    "productID": productID,
                    "productName": productName,
                    "productDescription": productDescription,
                    "size": size,
                    "color": color,
                    "category": category,
                    "quantity": quantity_to_order,
                    "warehouseID": warehouseID,
                    "vendorID": vendorID,
                    "vendorName": vendorName,
                    "orderDate": orderDate,
                    "expectedDate": expectedDate,
                }

                # send PO to vms
                response = await send_order_to_vms(po_payload)

                return{
                    "message": "Stock update processed. Purchase order created and sent to VMS.",
                    "payload": po_payload,
                    "response": response,
                }
        else:
            return {"message": "Stock update processed. No purchase order required."}
        
    except Exception as e:
        logging.error(f"error processing stock webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing stock webhook: {e}")
    finally:
        if conn:  # check if conn is not None before closing  
            await conn.close() 

def convert_decimal_to_json_compatible(data):
    if isinstance(data, dict):
        return {key: convert_decimal_to_json_compatible(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_decimal_to_json_compatible(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)  
    elif isinstance(data, datetime):  
        data.strftime('%Y-%m-%d %H:%M:%S')
    return data

# manual endpoint to create PO
@router.post('/create-purchase-order')
async def create_purchase_order(payload: dict):
    try:
        # extract payload fields
        productName = payload.get('productName')
        size = payload.get('size')
        category = payload.get('category')
        quantity = payload.get('quantity')
        warehouseName = payload.get('warehouseName')
        building = payload.get('building')
        street = payload.get('street')
        barangay = payload.get('barangay')
        city = payload.get('city')
        country = payload.get('country')
        zipcode = payload.get('zipcode')
        userID = payload.get('userID')

        # validate the payload 
        if not productName or not size or not category or not quantity or not warehouseName:
            raise HTTPException(status_code=400, detail="Invalid payload. Missing required fields.")
        
        conn = await database.get_db_connection()
        cursor = await conn.cursor()

        # fetch color (use default value 'Black' if not provided)
        color = 'Black'

        # execute stored procedure 
        await cursor.execute(
            "EXEC CreatePurchaseOrder ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
            (productName, size, category, quantity, warehouseName, building, street, barangay, city, country, zipcode, userID)
        )
        order = await cursor.fetchone()


        if not order:
            raise HTTPException(status_code=404, detail='Failed to create purchase order')
        
        orderID = order[0]

        await conn.commit()
        # fetch order details for VMS
        await cursor.execute('''
            SELECT po.orderID, po.orderDate, v.vendorID, v.vendorName, 
                   w.warehouseID, w.warehouseName, w.building, w.street, 
                   w.barangay, w.city, w.country, w.zipcode, 
                   p.productID, p.productName, p.productDescription, p.size, p.color, p.category,
                   pod.orderQuantity, pod.expectedDate, u.userID, u.firstName, u.lastName
            FROM PurchaseOrders po
            JOIN Vendors v ON po.vendorID = v.vendorID
            JOIN PurchaseOrderDetails pod ON po.orderID = pod.orderID
            JOIN Warehouses w ON pod.warehouseID = w.warehouseID
            JOIN ProductVariants pv ON pod.variantID = pv.variantID
            JOIN Products p ON pv.productID = p.productID
            JOIN Users u ON po.userID = u.userID
            WHERE po.orderID = ?;
        ''', (orderID,))

        order_details = await cursor.fetchone()

        if not order_details:
            raise HTTPException(status_code=404, detail="Order details not found.")

        (orderID, orderDate, vendorID, vendorName, warehouseID, warehouseName, building, street, 
         barangay, city, country, zipcode, productID, productName, productDescription, size, color, category,
         quantity, expectedDate, userID, firstName, lastName) = order_details
        
         # convert datetime values before JSON serialization
        orderDate = orderDate.strftime('%Y-%m-%d %H:%M:%S') if isinstance(orderDate, datetime) else orderDate
        expectedDate = expectedDate.strftime('%Y-%m-%d %H:%M:%S') if isinstance(expectedDate, datetime) else expectedDate    

        # prepare payload for VMS
        po_payload = {
            "orderID": orderID,
            "productID": productID,
            "productName": productName,
            "productDescription": productDescription,
            "size": size,
            "color": 'Black',
            "category": category,
            "quantity": quantity,
            "warehouseID": warehouseID,
            "warehouseName": warehouseName,
            "warehouseAddress": f"{building}, {street}, {barangay}, {city}, {country}, {zipcode}",
            "vendorID": vendorID,
            "vendorName": vendorName,
            "orderDate": orderDate,
            "expectedDate": expectedDate,
            "userID": userID,
            "userName": f"{firstName} {lastName}",
        }

        po_payload = convert_decimal_to_json_compatible(po_payload)

        # Send PO to VMS
        response = await send_order_to_vms(po_payload)

        return {
            "message": "Purchase order successfully created and sent to VMS.",
            "payload": po_payload,
            "response": response,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating purchase order: {str(e)}")

    finally:
        await conn.close()

# get all generated orders and their details
@router.get('/purchase-orders', response_model=List[dict])
async def get_purchase_orders():
    try:
        conn = await database.get_db_connection()
        cursor = await conn.cursor()
        await cursor.execute(
            ''''''
        )
        rows = await cursor.fetchall()

        # fetch column names
        columns = [column[0] for column in cursor.description]

        # convert rows to dictionary
        purchase_orders = [dict(zip(columns, row)) for row in rows]

        return purchase_orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error fetching purchase orders: {e}")
    finally:
        await conn.close()


@router.get('product-names')
async def get_product_names():
    try:
        conn = await database.get_db_connection()
        cursor = await conn.cursor()
        await cursor.execute(
            '''SELECT distinct productName FROM Products WHERE isActive = 1;'''
        )
        rows = await cursor.fetchall()

        return [row[0] for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error fetching product names: {e}")
    finally:
        await conn.close()


@router.get("/get-product-details/{product_name}")
async def get_product_details(product_name: str):
    """
    Fetch product details (productID, category) based on the given product name.
    """
    try:
        conn = await database.get_db_connection()
        cursor = await conn.cursor()

        query = """
            SELECT productID, productName, category 
            FROM Products 
            WHERE productName = ? AND isActive = 1;
        """
        await cursor.execute(query, (product_name,))
        row = await cursor.fetchone()

        if row:
            return {
                "productID": row[0],
                "productName": row[1],
                "category": row[2]
            }
        else:
            raise HTTPException(status_code=404, detail="Product not found.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching product details: {e}")

    finally:
        await conn.close()


@router.get('/current-user')
async def get_current_user_details(current_user: dict = Depends(get_current_active_user)):
    try:
        return {
            "userID": current_user.userID,  
            "firstName": current_user.firstName,
            "lastName": current_user.lastName,
            "username": current_user.username        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching current user: {str(e)}")

@router.get('/dropdown-data/products')
async def get_products():
    try:
        conn = await database.get_db_connection()
        cursor = await conn.cursor()
        await cursor.execute(
            '''SELECT distinct productName FROM Products WHERE isActive = 1;'''
        )
        products = [row[0] for row in await cursor.fetchall()]
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching products: {str(e)}")
    finally:
        await conn.close()

@router.get('/get-product-sizes/{product_name}')
async def get_product_sizes(product_name: str):
    try:
        conn = await database.get_db_connection()
        cursor = await conn.cursor()

        # debugging: print received product_name
        print(f"Fetching sizes for: {product_name}")

        await cursor.execute("EXEC GetProductSizes ?", (product_name,))
        sizes = await cursor.fetchall()

        if not sizes:
            raise HTTPException(status_code=404, detail="No sizes found for this product.")

        return {"sizes": [size[0] for size in sizes]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching product sizes: {str(e)}")
    finally:
        await conn.close()


@router.get('/dropdown-data/warehouses')
async def get_warehouses():
    try:
        conn = await database.get_db_connection()
        cursor = await conn.cursor()
        await cursor.execute(
            '''SELECT warehouseName, 
                   CONCAT(building, ', ', street, ', ', barangay, ', ', city, ', ', country, ', ', zipcode) AS fullAddress
            FROM Warehouses'''
        )
        warehouses = [{"warehouseName": row[0], "fullAddress": row[1]} for row in await cursor.fetchall()]
        return {"warehouses": warehouses}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching warehouses: {str(e)}")
    
    finally:
        await conn.close()
