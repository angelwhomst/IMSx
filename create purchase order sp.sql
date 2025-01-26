create procedure CreatePurchaseOrder
	@productName varchar(255),
	@size varchar(50),
	@category varchar(100),
	@quantity int,
	@warehouseName varchar(100),
    @building varchar(100),
    @street varchar(100),
    @barangay varchar(100),
    @city varchar(100),
    @country varchar(100),
    @zipcode varchar(100),
	@userID int

as
begin 
	set nocount on;

	declare @productID int, @vendorID int, @vendorName varchar(255), @variantID int, @warehouseID int;
	declare @orderID int, @orderDate datetime, @expectedDate datetime;
	set @orderDate = GETDATE();
	set @expectedDate = dateadd(day, 7, @orderDate);

	-- validate product existence and fetch productID 
	select top 1 @productID = productID
	from products
	where productName = @productName and category = @category;

	if @productID is null
	begin 
		raiserror ('Product not found for the given name and category.', 16, 1);
		return;
	end;

	-- fetch vendor
	select top 1 @vendorID = vendorID, @vendorName = vendorName
	from Vendors
	where isActive = 1;

	if @vendorID is null
	begin 
		raiserror ('No available product variant found for the given size.', 16, 1);
		return;
	end;
	-- Fetch Product Variant
    SELECT TOP 1 @variantID = variantID
    FROM ProductVariants
    WHERE productID = @productID and isAvailable = 1;

    IF @variantID IS NULL
    BEGIN
        RAISERROR ('No available product variant found for the given size.', 16, 1);
        RETURN;
    END;

    -- Fetch Warehouse ID based on provided location details
    SELECT TOP 1 @warehouseID = warehouseID
    FROM Warehouses
    WHERE warehouseName = @warehouseName
        AND building = @building
        AND street = @street
        AND barangay = @barangay
        AND city = @city
        AND country = @country
        AND zipcode = @zipcode;

    IF @warehouseID IS NULL
    BEGIN
        RAISERROR ('No warehouse found for the given details.', 16, 1);
        RETURN;
    END;

	-- insert into PurchaseOrders table
	insert into PurchaseOrders (orderDate, orderStatus, statusDate, vendorID, userID)
	output inserted.orderID 
	values (@orderDate, 'Pending', GETDATE(), @vendorID, @userID);

	set @orderID = IDENT_CURRENT('PurchaseOrders');

	-- insert into PurchaseOrderDetails
	insert into PurchaseOrderDetails (orderQuantity, expectedDate, warehouseID, orderID, variantID)
	values (@quantity, @expectedDate, @warehouseID, @orderID, @variantID);

	-- return orderID 
	select @orderID as orderID;
end;
go

-- ========================= addwarehouse
create procedure AddWarehouse
	@warehouseName varchar(255),
	@building varchar(255),
	@street varchar(255),
	@barangay varchar(255),
	@city varchar(255),
	@country varchar(255),
	@zipcode varchar(25)
as
begin
	set nocount on;

	insert into Warehouses (warehouseName, building, street, barangay, city, country, zipcode)
	output inserted.warehouseID
	values (@warehouseName, @building, @street, @barangay, @city, @country, @zipcode);
end;
go