if not exists (select name from sys.databases where name = N'IMS')
begin
create database IMS;
end

use IMS
go 

if object_id(N'dbo.Users', 'U') is null
begin
create table Users 
(userID numeric identity(1,1) constraint userID_PK primary key,
firstName varchar(50), 
lastName varchar(50), 
username varchar (50),
userPassword varchar(500),
userRole varchar(50),
isDisabled bit default 0,
createdAt datetime default getdate(),
updatedAt datetime default getdate()
)
end

if object_id(N'dbo.Warehouses', 'U') is null
begin 
create table Warehouses
(
warehouseID numeric identity(1,1) constraint warehouseID_PK primary key,
warehouseName varchar(100),
building varchar(100),
street varchar(100),
barangay varchar(100),
city varchar(100),
country varchar(100),
zipcode varchar(20))
end

if object_id(N'dbo.Products', 'U') is null
begin
create table Products
(productID numeric IDENTITY(1,1) constraint PK_productID PRIMARY KEY,
    productName VARCHAR(100) NOT NULL constraint UQ_productName unique,
    productDescription VARCHAR(255),
	size VARCHAR(20),
    color VARCHAR(20),
    category VARCHAR(50),
	unitPrice numeric,
	reorderLevel INT NOT NULL default 0,
	minStockLevel int not null default 0,
	maxStockLevel int not null default 0,
	currentStock int,
	createdAt DATETIME DEFAULT GETDATE(),
    lastUpdated DATETIME DEFAULT GETDATE(),
	isActive bit default 1,
	warehouseID numeric constraint FK_warehouseID_product foreign key references Warehouses(warehouseID)
)
end

if object_id(N'dbo.ProductVariants', 'U') is null
begin
CREATE TABLE ProductVariants (
    variantID numeric IDENTITY(1,1) constraint PK_variantID PRIMARY KEY,
    barcode VARCHAR(50),
    productCode VARCHAR(50),
	isDamaged bit default 0,
	isWrongItem bit default 0, 
	isReturned bit default 0,
	isAvailable bit default 1,
	productID numeric NOT NULL constraint FK_productID_variant FOREIGN KEY REFERENCES products(productID)
	on update cascade
	on delete cascade
)
end

if object_id('dbo.Vendors', 'U') is null
begin
create table Vendors
(
vendorID numeric identity(1,1) constraint vendorID_PK primary key,
vendorName varchar (100),
contactNumber char(11),
building varchar(100),
street varchar(100),
barangay varchar(100),
city varchar(100),
country varchar(100),
zipcode varchar(20),
isActive bit default 1
)
end

if object_id(N'dbo.PurchaseOrders', 'U') is null
begin 
create table PurchaseOrders
(
orderID numeric identity(1,1) constraint orderID_PK primary key,
orderDate datetime2,
orderStatus varchar (100),
statusDate datetime2,
vendorID numeric constraint vendorID_FK foreign key references vendors(vendorID),
userID numeric constraint FK_userID_PO foreign key references users(userID)
on update cascade
on delete cascade)
end

if object_id(N'dbo.PurchaseOrderDetails', 'U') is null
begin 
create table PurchaseOrderDetails
(
orderDetailID numeric identity(1,1) constraint orderDetailID_PK primary key,
orderQuantity numeric default 1,
expectedDate datetime2,
actualDate datetime2,
variantID numeric constraint variantID_FK_PO foreign key references productVariants(variantID),
warehouseID numeric constraint warehouseID_FK_PO foreign key references warehouses(warehouseID),
orderID numeric constraint orderID_FK foreign key references purchaseOrders(orderID)
on update cascade
on delete cascade)
end

-- Create Sales Table
if object_id(N'dbo.Sales', 'U') is null
begin
    create table Sales (
        salesID numeric identity(1,1) constraint PK_salesID primary key,
        userID numeric constraint FK_employeeID_sales foreign key references users(userID),
        salesDate datetime default getdate(),
        totalAmount numeric(18, 2) not null,
        createdAt datetime default getdate(),
        updatedAt datetime default getdate()
    )
end

-- Create SalesDetails Table
if object_id(N'dbo.SalesDetails', 'U') is null
begin
    create table SalesDetails (
        salesDetailID numeric identity(1,1) constraint PK_salesDetailID primary key,
        salesID numeric not null constraint FK_salesID_details foreign key references Sales(salesID) 
            on update cascade on delete cascade,
        variantID numeric not null constraint FK_variantID_salesDetail foreign key references ProductVariants(variantID),
        unitPrice numeric(18, 2) not null
    )
end

-- Create Cart Table (for pre-checkout actions)
if object_id(N'dbo.Cart', 'U') is null
begin
    create table Cart (
        cartID numeric identity(1,1) constraint PK_cartID primary key,
        userID numeric constraint FK_userID_cart foreign key references Users(userID),
        variantID numeric not null constraint FK_variantID_cart foreign key references ProductVariants(variantID),
        unitPrice numeric(18, 2) not null,
        createdAt datetime default getdate()
    )
end




/*

if object_id('dbo.Customers', 'U') is null
begin 
create table Customers
(
customerID numeric identity(1,1) constraint customerID_PK primary key,
lastName varchar(100),
firstName varchar(100),
building varchar(100),
street varchar(100),
barangay varchar(100),
city varchar(100),
country varchar(100),
zipcode varchar(20)),
contactNumber char(13) 
end

if object_id(N'dbo.Deliveries','U') is null
begin 
create table Deliveries 
(
deliveryID numeric identity(1,1) constraint deliveryID_PK primary key,
salesDate datetime2,
customerID numeric constraint customerID_FK foreign key references customers(customerID)
on delete cascade
on update cascade)
end

if object_id(N'dbo.DeliveryDetails', 'U') is null
begin 
create table DeliveryDetails
(
deliveryDetailID numeric identity(1,1) constraint deliveryDetailID_PK primary key,
quantity numeric default 1,
expectedDate date,
actualDate datetime2,
variantID numeric constraint variantID_FK_delivery foreign key references productVariants(variantID),
deliveryID numeric constraint deliveryID_FK foreign key references deliveries(deliveryID)
on update cascade
on delete cascade)
end

*/