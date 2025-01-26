from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
from pydantic import BaseModel
import httpx
import random
import string
import os
import base64
from typing import Optional
import logging
from fastapi.staticfiles import StaticFiles 
import database
from routers.auth import role_required, get_current_active_user

# Directory for saving uploaded images
UPLOAD_DIRECTORY = "images_upload"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# Function to generate a unique filename for images
def generate_image_filename():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16)) + ".png"

# Function to decode Base64 image and save to file
def save_base64_image(base64_image: str) -> str:
    try:
        # Decode the Base64 string
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]

        
        missing_padding = len(base64_image) % 4
        if missing_padding:
            base64_image += "=" * (4 - missing_padding)

        image_data = base64.b64decode(base64_image)
        filename = generate_image_filename()
        filepath = os.path.join(UPLOAD_DIRECTORY, filename)
        with open(filepath, "wb") as file:
            file.write(image_data)
        return filepath
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 image: {str(e)}")

# function to generate barcode
def generate_barcode():
    characters = string.ascii_uppercase + string.digits
    barcode = ''.join(random.choices(characters, k=13))
    return barcode

# function to generate sku
def generate_sku():
    characters = string.ascii_uppercase + string.digits
    sku = ''.join(random.choices(characters, k=8))
    return sku

router = APIRouter(dependencies=[Depends(role_required(["admin"]))])

# webhook url ---------------------

STOCK_WEBHOOK_URL = "http://127.0.0.1:8001/stock"

# pydantic model for products 
class Product(BaseModel):
    productName: str
    productDescription: Optional[str] = None
    size: str
    color: Optional[str] = None
    category: str
    unitPrice: float
    threshold: int = 0
    reorderLevel: int = 0
    minStockLevel: int = 0
    maxStockLevel: int = 0
    quantity: int = 1  # number of variants to add
    image: Optional[str] = None  # Base64 image string

# pydantic model for adding quantities to an existing product
class AddQuantity(BaseModel):
    productName: str
    size: str
    category: str
    quantity: int

# pydantic model for product variants
class ProductVariant(BaseModel):
    productName: str
    barcode: str
    productCode: str
    productDescription: str
    size: str
    color: Optional[str] = None
    unitPrice: float
    warehouseID: Optional[int] = None
    isDamaged: bool = False
    isWrongItem: bool = False
    isReturned: bool = False

class ProductQueryParams(BaseModel):
    productName: str
    productDescription: str
    unitPrice: float
    category: str

class ProductVariantResponse(BaseModel):
   size: str
   productCode: str
   barcode: str

class ProductUpdate(BaseModel):
    productName: str
    productDescription: str
    size: str
    category: str
    unitPrice: float
    newSize: str
    minStockLevel: int
    maxStockLevel: int
    reorderLevel: int
    threshold: int

    class Config:
        orm_mode = True

class ProductUpdates(BaseModel):
    productName: str  # Current product name
    productDescription: str  # Current product description
    category: str  # Current category
    unitPrice: float  # Current unit price
    newProductName: str  # New product name
    newProductDescription: str  # New product description
    newCategory: str  # New category
    newUnitPrice: float  # New unit price
    newImage: str  # New image URL or path

class ADDSIZE(BaseModel):
    productName: str
    productDescription: str
    size: str
    category: str
    unitPrice: float
    threshold: int
    reorderLevel: int
    minStockLevel: int
    maxStockLevel: int
    quantity: int
    image: str = None


# function to trigger stock webhook
async def trigger_stock_webhook(product_id: int, current_stock: int):
    async with httpx.AsyncClient() as client:
        try:
            # Ensure currentStock is treated as an integer
            payload = {"productID": product_id, "currentStock": int(current_stock)} 
            response = await client.post(STOCK_WEBHOOK_URL, json=payload)
            response.raise_for_status()  
        except Exception as e:
            print(f'Error sending stock webhook: {e}')

# create a new product with variants
@router.post('/products')
async def add_product(product: Product):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try:
        # Save Base64 image to file
        image_path = save_base64_image(product.image)

        # check if a product with the same details already exists
        await cursor.execute('''select productID from Products
                                where productname = ? and size=? and category=? 
                                and isActive=1''',
                             product.productName, product.size, product.category)
        existing_product = await cursor.fetchone()

        if existing_product:
            raise HTTPException(status_code=400, 
                                detail=f"A product with name '{product.productName}', size '{product.size}', and category '{product.category}' already exists.")
        
        # insert the new product
        await cursor.execute(''' insert into Products (
                                productName, productDescription, size, color, category,  
                                unitPrice, threshold, reorderLevel, minStockLevel, maxStockLevel, currentStock, image_path)
                                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);''',
                             product.productName,
                             product.productDescription,
                             product.size,
                             product.color,
                             product.category,
                             float(product.unitPrice),  
                             product.threshold,
                             product.reorderLevel,
                             product.minStockLevel,
                             product.maxStockLevel,
                             product.quantity,
                             image_path)
        await conn.commit()

        # get the last inserted productID
        await cursor.execute("select IDENT_CURRENT('Products')")
        product_id_row = await cursor.fetchone()
        product_id = product_id_row[0] if product_id_row else None

        if not product_id:
            raise HTTPException(status_code=500, detail='Failed to retrieve productID after insertion')

        # insert multiple variants/quantity into productVariants table
        variants_data = [
            (generate_barcode(), generate_sku(), product_id)
            for _ in range(product.quantity)
        ]
        
        await cursor.executemany(''' insert into ProductVariants (barcode, productCode, productID)
                                      values (?, ?, ?);''', variants_data)
        await conn.commit()

        # trigger the stock webhook with the unitPrice converted to float
        await trigger_stock_webhook(product_id, float(product.unitPrice))

        return {'message': f'Product {product.productName} added with {product.quantity} variants.'}
    
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        await conn.close()

# add quantities to an existing products
@router.post('/products/add-quantity')
async def add_product_quantity(product: AddQuantity):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        await cursor.execute(
            ''' select productID, currentStock
            from Products
            where productName = ? and size = ? and category=? 
            and isActive = 1''',
            product.productName,
            product.size,
            product.category
        )
        product_row = await cursor.fetchone()

        if not product_row:
            raise HTTPException(status_code=404, detail='Product not found.')

        product_id, current_stock = product_row

        # add new variant to ProductVariants table 
        variants_data= [(
                    generate_barcode(),
                    generate_sku(),
                    product_id )
                 for _ in range(product.quantity)
                 ]
        await cursor.executemany(
                    '''insert into ProductVariants (barcode, productCode, productID)
                    values (?, ?, ?)''',
                    variants_data
                )
        
        # update currentStock in Products tabel
        new_stock = current_stock + product.quantity
        await cursor.execute(
            '''update Products set currentStock = ? where productID =?''',
            new_stock, product_id
        )

        await conn.commit()

        # trigger the stock webhook
        await trigger_stock_webhook(product_id, new_stock)

        return{'message': f'{product.quantity} quantities of {product.productName} added successfully.'}
    
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

@router.post('/products/update')
async def update_product(productData: ProductUpdate):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        # step 1: select the productID based on the given fields
        await cursor.execute(
            '''
            select productID, productName, productDescription, size, category, unitPrice, minStockLevel, maxStockLevel, reorderLevel, threshold 
            from Products 
            where productName = ? AND productDescription = ? AND size = ? AND category = ? AND unitPrice = ? AND isActive = 1''',
            productData.productName, productData.productDescription,productData.size, productData.category,float(productData.unitPrice))
        
        product_row = await cursor.fetchone()
        if not product_row:
            raise HTTPException(
                status_code=404,
                detail=f"Product with name '{productData.productName}', description '{productData.productDescription}', "
                       f"size '{productData.size}', category '{productData.category}', and unit price '{productData.unitPrice}' not found."
            )
        
        # extract the product ID
        product_id = product_row[0]

        # step 2: update the specific fields
        await cursor.execute('''update Products
                                 set size = ?, minStockLevel = ?, maxStockLevel = ?,
                                     reorderLevel = ?, threshold = ?
                                 where productID = ? AND isActive = 1''',
                             productData.newSize,
                             productData.minStockLevel,
                             productData.maxStockLevel,
                             productData.reorderLevel,
                             productData.threshold,
                             product_id)
        await conn.commit()

        # step 3: return success message with updated data
        return {"message": f"Product with ID {product_id} updated successfully.",
                "updated_product": {
                    "productID": product_id,
                    "newSize": productData.newSize,
                    "minStockLevel": productData.minStockLevel,
                    "maxStockLevel": productData.maxStockLevel,
                    "reorderLevel": productData.reorderLevel,
                    "threshold": productData.threshold
                }}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

# add a new size to an existing product
@router.post('/products/add-size')
async def add_size(product: ADDSIZE):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        # step 1: check if product exists
        await cursor.execute(
            '''SELECT 1
            FROM Products
            WHERE productName = ? AND productDescription = ? AND size = ? AND isActive = 1''',
            product.productName, product.productDescription, product.size)
        
        existing_product = await cursor.fetchone()

        if existing_product:
            raise HTTPException(
                status_code=400,
                detail=f"Product with name '{product.productName}', description '{product.productDescription}', and size '{product.size}' already exists."
            )
        
        # step 2: save base64 image to file
        image_path = None
        if product.image:
            image_path = save_base64_image(product.image)   

        # step 3: insert the new size (which allows different sizes for the same product name and category)
        await cursor.execute(
            '''
            INSERT INTO Products (productName, productDescription, size, category, unitPrice, threshold, reorderLevel, minStockLevel, maxStockLevel, currentStock, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);''',
            product.productName, product.productDescription, product.size, product.category, float(product.unitPrice), product.threshold, product.reorderLevel, product.minStockLevel, product.maxStockLevel, product.quantity, image_path
        )
        await conn.commit()

        # step 4: get the last inserted productID
        await cursor.execute("SELECT IDENT_CURRENT('Products')")
        product_id_row = await cursor.fetchone()
        product_id = product_id_row[0] if product_id_row else None

        if not product_id:
            raise HTTPException(status_code=500, detail='Failed to retrieve productID after insertion')
        
        # step 5: insert multiple variants/quantity into productVariants table
        variants_data = [
            (generate_barcode(), generate_sku(), product_id)
            for _ in range(product.quantity)
        ]
        await cursor.executemany(
            '''INSERT INTO ProductVariants (barcode, productCode, productID)
            values (?, ?, ?);''', variants_data )
        await conn.commit()

        # step 6: trigger the stock webhook with the unitPrice converted to float
        await trigger_stock_webhook(product_id, float(product.unitPrice))

        return {'message': f'Product {product.productName} added with {product.quantity} variants.'}
    
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

# get all sizes of a product
@router.get('/products/sizes')
async def get_size(productName: str, unitPrice: float, category: str, productDescription: Optional[str] = None):
    conn = await database.get_db_connection()
    try:
        async with conn.cursor() as cursor:
            # SQL query to fetch all sizes with the same field names used in the frontend code
            await cursor.execute(''' 
                SELECT size, currentStock AS quantity, minStockLevel AS minQuantity, maxStockLevel AS maxQuantity, reorderLevel AS reorderQuantity, threshold AS threshold
                FROM Products 
                WHERE productName = ? 
                AND unitPrice = ? 
                AND category = ?
                AND (productDescription = ? OR ? IS NULL)
            ''', (productName, unitPrice, category, productDescription, productDescription))
            
            products = await cursor.fetchall()

            if products:
                # Map the query results to a list of dictionaries with the field names used in the frontend
                size_list = [
                    {"size": product[0], "quantity": product[1], "minQuantity": product[2], "maxQuantity": product[3], "reorderQuantity": product[4], "threshold": product[5]}
                    for product in products
                ]
                return {"size": size_list}  
            else:
                raise HTTPException(status_code=404, detail="Product not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

@router.get('/products/size_variants', response_model=list[ProductVariantResponse])
async def get_size_variants(productName: str, unitPrice: float, category: str, productDescription: Optional[str] = None):
    conn = await database.get_db_connection()
    #cursor = await conn.cursor()

    try:
     async with conn.cursor() as cursor:

        await cursor.execute(
            '''SELECT p.size, pv.productCode, pv.barcode
                FROM
                    Products AS p
                INNER JOIN
                    ProductVariants AS pv
                ON
                    p.productID = pv.productID
                WHERE
                    p.isActive = 1
                    AND pv.isAvailable = 1
                    AND p.productName = ?
                    AND (p.productDescription = ? OR ? IS NULL)
                    AND p.unitPrice = ?
                    AND p.category = ?;  
            ''', (productName, productDescription, productDescription, unitPrice, category))
        variants = await cursor.fetchall()

        if variants:
            variant_list = [
                {
                    "size": variant[0],
                    "productCode": variant[1],
                    "barcode": variant[2]
                }
                for variant in variants
            ]
            return variant_list
        else:
            raise HTTPException(status_code=404, detail="Product not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:    
        await conn.close()

#update product details such as name, description, category, unit price, and image
@router.put('/products/update-details')
async def update_product_details(productData: ProductUpdates):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()

    try:
        # step 1: select the productID based on the given fields
        await cursor.execute(
            '''select productID, productName, productDescription, category, unitPrice, image_path
            from Products
            where productName = ? and productDescription = ? and category = ? and unitPrice = ? and isActive = 1''',
            productData.productName, productData.productDescription, productData.category, float(productData.unitPrice)
        )
        product_row = await cursor.fetchone()

        if not product_row:
            raise HTTPException(
                status_code=404,
                detail=f"Product with name '{productData.productName}', description '{productData.productDescription}', "
                       f"category '{productData.category}', and unit price '{productData.unitPrice}' not found."
            )
        
        # extract the product ID
        product_id = product_row[0]

        # step 2: update the specific fields
        await cursor.execute(
            '''update Products
            set productName = ?, productDescription = ?, category = ?, unitPrice = ?
            where productID = ? AND isActive = 1''',
            productData.newProductName, productData.newProductDescription, productData.newCategory, float(productData.newUnitPrice), product_id)
        await conn.commit()

        # fetch the updated product 
        await cursor.execute(
            '''
            select productName, productDescription, category, unitPrice, image_path
            from Products
            where productID = ? and isActive = 1''', (product_id,))
        updated_product = await cursor.fetchone()

        return {"message": f"Product with ID {product_id} updated successfully.",
                "updated_product": {
                    "productName": updated_product[0],
                    "productDescription": updated_product[1],
                    "category": updated_product[2],
                    "unitPrice": updated_product[3],
                    "image_path": updated_product[4]
                }}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

# get all productss 
@router.get("/products")
async def get_products():
    conn = await database.get_db_connection()
    try: 
        async with conn.cursor() as cursor:
            await cursor.execute('''
select p.productName, p.productDescription,
p.size, p.unitPrice,
count(pv.variantID) as 'available quantity', p.currentStock,
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.threshold,
cast(p.image_path as varchar(max)) as image_path
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1
group by p.productName, p.productDescription, p.size, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.currentStock, p.threshold, cast(p.image_path as varchar(max));
''')
            products = await cursor.fetchall()
            # map column names to row values
            return [dict(zip([column[0] for column in cursor.description], row)) for row in products]
    finally: 
        await conn.close()


# get all Womens products
@router.get("/products/Womens-Leather-Shoes")
async def get_womens_products():
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try: 
        await cursor.execute(
            '''select p.productName, p.productDescription, p.category,
p.size, p.unitPrice, cast(p.image_path as varchar(max)),
count(pv.variantID) as 'available quantity', p.currentStock,
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.threshold
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1  and p.category = 'Women''s Leather Shoes'
group by p.productName, p.productDescription, p.category, p.size, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.currentStock, p.threshold, cast(p.image_path as varchar(max))
'''
        )
        products = await cursor.fetchall()
        # map column names to row values
        return [dict(zip([column[0] for column in cursor.description], row)) for row in products]
    finally: 
        await conn.close()

# get all Mens products
@router.get("/products/Mens-Leather-Shoes")
async def get_mens_products():
    logging.info("Received request for Men's Leather Shoes products")

    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try: 
        await cursor.execute(
            '''select p.productName, p.productDescription, p.category,
p.size, p.unitPrice, cast(p.image_path as varchar(max)) AS image_path,
count(pv.variantID) as 'available quantity', p.currentStock,
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.threshold
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1  and p.category = 'Men''s Leather Shoes'
group by p.productName, p.productDescription, p.category, p.size, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.currentStock, p.threshold, cast(p.image_path as varchar(max))
'''
)
        products = await cursor.fetchall()
        # map column names to row values
        return [dict(zip([column[0] for column in cursor.description], row)) for row in products]
    finally: 
        await conn.close()

# get all boy's leather shoes
@router.get("/products/Boys-Leather-Shoes") 
async def get_boys_products():
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try: 
        await cursor.execute(
            '''select p.productName, p.productDescription, p.category,
p.size, p.unitPrice, cast(p.image_path as varchar(max)),
count(pv.variantID) as 'available quantity', p.currentStock,
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.threshold
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1  and p.category = 'Boy''s Leather Shoes'
group by p.productName, p.productDescription, p.category, p.size, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.currentStock, p.threshold, cast(p.image_path as varchar(max))
'''
)
        products = await cursor.fetchall()
        # map column names to row values
        return [dict(zip([column[0] for column in cursor.description], row)) for row in products]
    finally: 
        await conn.close()

# get all girl's leather shoes
@router.get("/products/Girls-Leather-Shoes")
async def get_girls_products():
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try: 
        await cursor.execute(
            '''select p.productName, p.productDescription, p.category,
p.size, p.unitPrice, cast(p.image_path as varchar(max)),
count(pv.variantID) as 'available quantity', p.currentStock,
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.threshold
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1  and p.category = 'Girl''s Leather Shoes'
group by p.productName, p.productDescription, p.category, p.size, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.currentStock, p.threshold, cast(p.image_path as varchar(max))
'''
)
        products = await cursor.fetchall()
        # map column names to row values
        return [dict(zip([column[0] for column in cursor.description], row)) for row in products]
    finally: 
        await conn.close()

# get one product
@router.get('/products/{product_id}')
async def get_product(product_id: int):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try:
        await cursor.execute('''select p.productName, p.productDescription,
p.size, p.unitPrice, cast(p.image_path as varchar(max)),
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.warehouseID,
count(pv.variantID) as 'available quantity'
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.productID = ? and p.isActive = 1 and pv.isAvailable =1
group by p.productName, p.productDescription, p.size, p.color, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, cast(p.image_path as varchar(max))l''', (product_id,)
)
        product = await cursor.fetchone()
        if not product:
            raise HTTPException(status_code=404, detail='product not found')
        return dict(zip([column[0] for column in cursor.description], product))
    finally:
        await conn.close()

# get all product variants 
@router.get("/product/variants")
async def get_product_variants():
    conn = await database.get_db_connection()
    try: 
        async with conn.cursor() as cursor:
            await cursor.execute('''
select p.productName, pv.barcode, pv.productCode, 
p.productDescription, p.size, p.color, p.unitPrice, p.warehouseID,
p.reorderLevel, p.minStockLevel, p.maxStockLevel
from Products as p
full outer join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable = 1;''')
            products = await cursor.fetchall()
            # map column names to row values
            return [dict(zip([column[0] for column in cursor.description], row)) for row in products]
    finally: 
        await conn.close()

# get one product variant
@router.get('/products/variant/{variant_id}', response_model=ProductVariant)
async def get_product(variant_id: int):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try:
        await cursor.execute('''select p.productName, pv.barcode, pv.productCode, 
p.productDescription, p.size, p.color, p.unitPrice, p.warehouseID,
p.reorderLevel, p.minStockLevel, p.maxStockLevel
from Products as p
full outer join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable = 1
and pv.variantID = ?''', variant_id)
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='product variant not found')
        
        product_variant = ProductVariant(
            productName=row[0],
            barcode=row[1],
            productCode=row[2],
            productDescription=row[3],
            size=row[4],
            color=row[5],
            unitPrice=row[6],
            warehouseID=row[7],
            reorderLevel=row[8],
            minStockLevel=row[9],
            maxStockLevel=row[10]
        )
        return product_variant
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()


# update a product
@router.put('/products/{product_id}')
async def update_product(product_id: int, product: Product):
    conn = await database.get_db_connection()
    try:
        async with conn.cursor() as cursor:
            await cursor.execute(
            '''
update Products
set productName = ?, productDescription = ?, size = ?, color = ?, category = ?, unitPrice = ?, 
reorderLevel = ?, minStockLevel = ?, maxStockLevel = ?
where productID = ? ''',
            product.productName,
            product.productDescription,
            product.size,
            product.color,
            product.category,
            product.unitPrice,
            product.reorderLevel,
            product.minStockLevel,
            product.maxStockLevel,
            product_id,
        )
            await conn.commit()
            return{'message': 'product updated successfully!'}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

# delete a product
@router.delete('/products/{product_id}')
async def delete_product(product_id: int):
    conn = await database.get_db_connection()
    try:
        async with conn.cursor() as cursor:
            await cursor.execute('''update ProductVariant
                       set isActive=0
                       where productID = ?''', product_id)
            await conn.commit()
            return {'message': 'product deleted successfully'}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

# soft delete a product variant
@router.delete('/products/variant/{variant_id}')
async def delete_product_variant(variant_id: int):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try:
        # get the productID of the variant to be deleted
        await cursor.execute(
            '''select productID from ProductVariants
               where variantID = ? AND isAVailable = 1''',
            variant_id
        )
        variant_row = await cursor.fetchone()

        if not variant_row:
            raise HTTPException(status_code=404, detail="Product variant not found or already deleted.")

        product_id = variant_row[0]

        # soft delete the product variant
        await cursor.execute('''update productVariants
                    set isAvailable = 0
                    where variantID = ?''', variant_id)
        
        # decrease currentStock in Products table
        await cursor.execute(
            '''update Products
            set currentStock = currentStock - 1
            where productID = ?''', product_id
        )
        await conn.commit()

        # get the updated stock
        await cursor.execute(
            'select currentStock from Products where productID =?', product_id)
        updated_stock_row = await cursor.fetchone()
        updated_stock = updated_stock_row[0] if updated_stock_row else 0

        # trigger teh stock webhook with updated stock level
        await trigger_stock_webhook(product_id, updated_stock)

        return {'message': 'Product variant deleted successfully'}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()
