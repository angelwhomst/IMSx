
-- get all product variants
create view vw_all_variants
as 
select p.productName, pv.barcode, pv.productCode, 
p.productDescription, p.size, p.color, p.unitPrice, p.warehouseID,
p.reorderLevel, p.minStockLevel, p.maxStockLevel
from Products as p
full outer join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable = 1;
go 

-- get one product variant
create procedure get_one_variant
@variantID numeric
as
begin
select * from vw_all_variants
where barcode in (select barcode from ProductVariants where variantID = @variantID);
end
go
-- exec get_one_variant @variantID = ?


-- get all products
create procedure get_all_products
as 
select p.productName, p.productDescription,
p.size, p.color, p.unitPrice, p.warehouseID,
count(pv.variantID) as 'available quantity', p.currentStock,
p.reorderLevel, p.minStockLevel, p.maxStockLevel
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1
group by p.productName, p.productDescription, p.size, p.color, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.currentStock, p.productID
order by p.productID;
go

exec get_all_products
go

-- get one product
create procedure get_one_product
@productID numeric
as 
select p.productName, p.productDescription,
p.size, p.color, p.unitPrice, 
p.reorderLevel, p.minStockLevel, p.maxStockLevel, p.warehouseID,
count(pv.variantID) as 'available quantity'
from products as p
left join ProductVariants as pv
on p.productID = pv.productID
where p.isActive = 1 and pv.isAvailable =1 and p.productID = @productID
group by p.productName, p.productDescription, p.size, p.color, p.unitPrice, p.warehouseID, p.reorderLevel, p.minStockLevel, p.maxStockLevel 
go

-- exec get_one_product @productID =? 

-- get sales history
create procedure EmployeeSalesHistory
@userID numeric
as
begin
select p.productName, p.category, p.size,
count(sd.salesdetailID) as totalQuantitySold,
format(count(sd.salesdetailID) * p.unitPrice, 'N', 'en-US') as totalAmount,
s.salesDate
from Sales as s 
inner join SalesDetails as sd
on s.salesID = sd.salesID
inner join ProductVariants as pv
on sd.variantID = pv.variantID
inner join Products as p
on pv.productID = p.productID
where s.userID = 7
group by p.productname, p.category, p.size, s.salesDate, p.unitPrice
order by s.salesDate desc
end
go


-- get products per category for the dropdown in sales logic
create procedure GetProductByCategory
	@category varchar(100) -- select category from dropdown
as 
begin
	set nocount on;

	if @category = 'All Categories'
	begin
		-- fetch all available products
		select p.productName, p.size, p.unitPrice,
		cast(p.image_path as varchar(max)) as image_path
		from Products as p
		left join ProductVariants as pv
			on p.productID = pv.productID
		where p.isActive =1
			and pv.isAvailable=1
		group by p.productName, p.size, p.unitPrice, p.productID,
				cast(p.image_path as varchar(max))
		order by p.productID desc;
	end
	else 
	begin
		--fetch products by specific category
		select p.productName, p.size, p.unitPrice,
		cast(p.image_path as varchar(max)) as image_path
		from Products as p
		left join ProductVariants as pv
			on p.productID = pv.productID
		where p.isActive =1
			and pv.isAvailable=1
			and p.category = @category
		group by p.productName, p.size, p.unitPrice, p.productID,
				cast(p.image_path as varchar(max))
		order by p.productID desc;
	end
	set nocount off;
end;
go

create procedure get_all_orderStatus
as
begin
select p.productName, p.category, p.size,
pod.orderQuantity,
format((pod.orderQuantity * p.unitPrice), 'N', 'en-US')as [total price],
po.statusDate, po.orderStatus
from 
	PurchaseOrders as po
left join 
	PurchaseOrderDetails as pod on po.orderID = pod.orderID
left join  
    productvariants pv on pod.variantid = pv.variantid
left join 
    products p on pv.productid = p.productid
order by po.orderDate desc
end
go

create procedure get_orders_by_status
@orderStatus varchar(50)
as
begin
select p.productName, p.size, p.category,
pod.orderQuantity,
format((pod.orderQuantity * p.unitPrice), 'N', 'en-US')as [total price],
po.statusDate, po.orderStatus
from 
	PurchaseOrders as po
left join 
	PurchaseOrderDetails as pod on po.orderID = pod.orderID
left join  
    productvariants pv on pod.variantid = pv.variantid
left join 
    products p on pv.productid = p.productid
where po.orderStatus = @orderStatus
order by po.orderDate desc
end
go



create proc get_delivered_orders_with_orderid
as
SELECT 
                po.orderID,                       -- Include orderID
                p.productName, 
                p.category, 
                p.size, 
                pod.orderQuantity,
                FORMAT((pod.orderQuantity * p.unitPrice), 'N', 'en-US') AS [total price],
                po.statusDate, 
                po.orderStatus
            FROM 
                PurchaseOrders AS po
            LEFT JOIN 
                PurchaseOrderDetails AS pod ON po.orderID = pod.orderID
            LEFT JOIN 
                productVariants pv ON pod.variantid = pv.variantid
            LEFT JOIN 
                Products p ON pv.productid = p.productid
            WHERE 
                po.orderStatus = 'Delivered'
            ORDER BY 
                po.orderDate DESC
			