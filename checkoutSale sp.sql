create procedure CheckoutSale
	@userID numeric,
	@variantIDList varchar(max) -- comma-separated list of variantIDs
as
begin
	begin transaction;

	begin try
		--------------
		-- CREATE A NEW SALE
		--------------
		declare @salesID numeric;
		declare @TempSalesID table (salesID numeric) -- temporary table to capture output

		insert into Sales (userID, totalAmount)
		output inserted.salesID into @TempSalesID(salesID)
		values (@userID, 0); -- 0 for TotalAmount which will be updated later

		-- retrieve the salesID
		select @salesID = salesID from @TempSalesID;

		--------------
		-- PROCESS EACH variantID
		--------------
		declare @variantID numeric;
		declare @unitPrice numeric (18, 2);
		declare @productID numeric;

		-- parse the variantID list
		declare variant_cursor cursor for
		select value from string_split(@variantIDList, ','); -- this parses the comma-separated list from @tempsalesid table earlier

		open variant_cursor;
		fetch next from variant_cursor into @variantID;

		while @@FETCH_STATUS = 0 
		begin 
		--	get the productID and unitPrice of the variant
			select @productID = pv.productID,
			@unitPrice = p.unitPrice
			from ProductVariants as pv
			join Products as p
			on pv.productID = p.productID
			where pv.variantID = @variantID;

			-- insert into SalesDetails 
			insert into SalesDetails (salesID, variantID, unitPrice)
			values (@salesID, @variantID, @unitPrice);

			-- mark teh variant as unavailable
			update ProductVariants
			set isAvailable = 0
			where variantID= @variantID;

			-- update Products.currentStock
			update Products
			set currentStock = currentStock - 1 -- decrease by 1 for each variant
			where productID = @productID

			fetch next from	variant_cursor into @variantID;
		end;

		close variant_cursor;
		deallocate variant_cursor;

		--------------
		-- UPDATE TotalAmount in Sales
		--------------
		update Sales
		set totalAmount = (
			select sum(sd.unitPrice)
			from SalesDetails as sd
			where sd.salesID = @salesID )
		where salesID = @salesID;

		-- COMMIT THE TRANSACTION YEHEY
		commit transaction;
	end try

	begin catch 
		-- rollback transaction in case of error
		rollback transaction;
		throw;
	end catch;

end;

