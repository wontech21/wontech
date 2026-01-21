-- Sample data for Firing Up Food Production Inventory

-- Insert sample suppliers
INSERT INTO suppliers (supplier_name, contact_person, phone, email, payment_terms) VALUES
('Fresh Produce Wholesalers', 'Maria Garcia', '555-1001', 'maria@freshproduce.com', 'Net 30'),
('Sysco Foods', 'John Martinez', '555-1002', 'jmartinez@sysco.com', 'Net 15'),
('US Foods', 'Sarah Chen', '555-1003', 'schen@usfoods.com', 'Net 30'),
('Restaurant Depot', 'Mike Johnson', '555-1004', 'mjohnson@restaurantdepot.com', 'COD'),
('Packaging Solutions Inc', 'Lisa Brown', '555-1005', 'lbrown@packagingsolutions.com', 'Net 30');

-- Insert sample ingredients
INSERT INTO ingredients (ingredient_code, ingredient_name, category, unit_of_measure, quantity_on_hand, unit_cost, supplier_name, reorder_level, reorder_quantity, storage_location) VALUES
-- Produce
('ING-TOM-001', 'Roma Tomatoes', 'Produce', 'lbs', 50, 2.50, 'Fresh Produce Wholesalers', 20, 50, 'Walk-in Cooler A'),
('ING-ONI-001', 'Yellow Onions', 'Produce', 'lbs', 30, 1.25, 'Fresh Produce Wholesalers', 15, 40, 'Walk-in Cooler A'),
('ING-GAR-001', 'Fresh Garlic', 'Produce', 'lbs', 10, 3.75, 'Fresh Produce Wholesalers', 5, 15, 'Walk-in Cooler A'),
('ING-LET-001', 'Iceberg Lettuce', 'Produce', 'heads', 24, 1.50, 'Fresh Produce Wholesalers', 12, 24, 'Walk-in Cooler A'),
('ING-JAL-001', 'Jalapeño Peppers', 'Produce', 'lbs', 8, 2.00, 'Fresh Produce Wholesalers', 5, 10, 'Walk-in Cooler A'),

-- Meat & Protein
('ING-BEF-001', 'Ground Beef 80/20', 'Meat', 'lbs', 100, 4.50, 'Sysco Foods', 40, 100, 'Walk-in Cooler B'),
('ING-CHK-001', 'Chicken Breast', 'Meat', 'lbs', 60, 3.25, 'Sysco Foods', 30, 80, 'Walk-in Cooler B'),
('ING-POR-001', 'Pulled Pork', 'Meat', 'lbs', 40, 5.75, 'Sysco Foods', 20, 50, 'Walk-in Cooler B'),

-- Dairy
('ING-CHE-001', 'Cheddar Cheese', 'Dairy', 'lbs', 25, 5.25, 'US Foods', 15, 30, 'Walk-in Cooler C'),
('ING-SCR-001', 'Sour Cream', 'Dairy', 'gallons', 5, 12.50, 'US Foods', 3, 6, 'Walk-in Cooler C'),

-- Dry Goods
('ING-FLO-001', 'All-Purpose Flour', 'Dry Goods', 'lbs', 200, 0.45, 'Restaurant Depot', 50, 200, 'Dry Storage A'),
('ING-TOR-001', 'Flour Tortillas (10-inch)', 'Dry Goods', 'dozen', 50, 3.00, 'US Foods', 20, 60, 'Dry Storage A'),
('ING-BUN-001', 'Burger Buns', 'Dry Goods', 'dozen', 30, 2.50, 'US Foods', 15, 40, 'Dry Storage A'),
('ING-RIC-001', 'White Rice', 'Dry Goods', 'lbs', 100, 0.75, 'Restaurant Depot', 40, 100, 'Dry Storage A'),
('ING-BEA-001', 'Black Beans (dried)', 'Dry Goods', 'lbs', 50, 1.20, 'Restaurant Depot', 20, 50, 'Dry Storage A'),

-- Spices & Seasonings
('ING-CUM-001', 'Ground Cumin', 'Spices', 'oz', 32, 0.85, 'Restaurant Depot', 16, 32, 'Spice Rack'),
('ING-CHI-001', 'Chili Powder', 'Spices', 'oz', 48, 0.65, 'Restaurant Depot', 24, 48, 'Spice Rack'),
('ING-SAL-001', 'Salt', 'Spices', 'lbs', 20, 0.50, 'Restaurant Depot', 10, 25, 'Spice Rack'),
('ING-PEP-001', 'Black Pepper', 'Spices', 'oz', 32, 1.25, 'Restaurant Depot', 16, 32, 'Spice Rack'),

-- Packaging
('PKG-BOX-001', 'To-Go Boxes (9x6)', 'Packaging', 'units', 500, 0.35, 'Packaging Solutions Inc', 200, 500, 'Packaging Area'),
('PKG-CUP-001', 'Sauce Cups 2oz', 'Packaging', 'units', 1000, 0.08, 'Packaging Solutions Inc', 400, 1000, 'Packaging Area'),
('PKG-BAG-001', 'Paper Bags', 'Packaging', 'units', 300, 0.15, 'Packaging Solutions Inc', 150, 400, 'Packaging Area');

-- Insert sample finished products
INSERT INTO products (product_code, product_name, category, unit_of_measure, quantity_on_hand, selling_price, shelf_life_days, storage_requirements) VALUES
('PRD-TAC-001', 'Beef Tacos (3-pack)', 'Entrees', 'each', 0, 12.99, 1, 'Hot Hold 140°F+'),
('PRD-BUR-001', 'Chicken Burrito', 'Entrees', 'each', 0, 10.99, 1, 'Hot Hold 140°F+'),
('PRD-BRG-001', 'Classic Burger', 'Entrees', 'each', 0, 9.99, 1, 'Hot Hold 140°F+'),
('PRD-RIC-001', 'Spanish Rice (side)', 'Sides', 'lbs', 0, 3.99, 2, 'Refrigerate 41°F or below'),
('PRD-BEA-001', 'Black Beans (side)', 'Sides', 'lbs', 0, 3.99, 3, 'Refrigerate 41°F or below'),
('PRD-SAL-001', 'Pico de Gallo', 'Sauces', 'lbs', 0, 5.99, 2, 'Refrigerate 41°F or below');

-- Insert sample recipes (what goes into each product)
-- Beef Tacos (3-pack)
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes) VALUES
(1, 6, 0.5, 'lbs', 'Seasoned ground beef'),
(1, 12, 0.25, 'dozen', '3 tortillas per order'),
(1, 9, 0.125, 'lbs', 'Shredded cheese'),
(1, 4, 0.05, 'heads', 'Shredded lettuce'),
(1, 1, 0.1, 'lbs', 'Diced tomatoes'),
(1, 20, 1, 'units', 'To-go box');

-- Chicken Burrito
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes) VALUES
(2, 7, 0.4, 'lbs', 'Grilled chicken'),
(2, 12, 0.083, 'dozen', '1 large tortilla'),
(2, 14, 0.25, 'lbs', 'Spanish rice'),
(2, 15, 0.2, 'lbs', 'Black beans'),
(2, 9, 0.1, 'lbs', 'Shredded cheese'),
(2, 10, 0.05, 'gallons', 'Sour cream'),
(2, 20, 1, 'units', 'To-go box');

-- Classic Burger
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes) VALUES
(3, 6, 0.33, 'lbs', '1/3 lb patty'),
(3, 13, 0.083, 'dozen', '1 burger bun'),
(3, 9, 0.05, 'lbs', 'Cheese slice'),
(3, 4, 0.02, 'heads', 'Lettuce'),
(3, 1, 0.05, 'lbs', 'Sliced tomato'),
(3, 2, 0.02, 'lbs', 'Sliced onion'),
(3, 20, 1, 'units', 'To-go box');

-- Spanish Rice (side, makes 5 lbs batch)
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes) VALUES
(4, 14, 3, 'lbs', 'Cooked rice'),
(4, 1, 1, 'lbs', 'Diced tomatoes'),
(4, 2, 0.5, 'lbs', 'Diced onions'),
(4, 3, 0.1, 'lbs', 'Minced garlic'),
(4, 16, 2, 'oz', 'Cumin'),
(4, 18, 0.5, 'lbs', 'Salt to taste');

-- Black Beans (side, makes 5 lbs batch)
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes) VALUES
(5, 15, 3, 'lbs', 'Cooked black beans'),
(5, 2, 0.3, 'lbs', 'Diced onions'),
(5, 3, 0.1, 'lbs', 'Minced garlic'),
(5, 16, 1, 'oz', 'Cumin'),
(5, 18, 0.3, 'lbs', 'Salt to taste');

-- Pico de Gallo (makes 3 lbs batch)
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure, notes) VALUES
(6, 1, 2, 'lbs', 'Diced tomatoes'),
(6, 2, 0.5, 'lbs', 'Diced onions'),
(6, 5, 0.2, 'lbs', 'Diced jalapeños'),
(6, 3, 0.05, 'lbs', 'Minced garlic'),
(6, 18, 0.1, 'lbs', 'Salt to taste');

-- Insert sample ingredient transactions
INSERT INTO ingredient_transactions (ingredient_id, transaction_type, quantity_change, unit_cost, notes) VALUES
(1, 'PURCHASE', 50, 2.50, 'Weekly delivery from Fresh Produce'),
(2, 'PURCHASE', 30, 1.25, 'Weekly delivery'),
(6, 'PURCHASE', 100, 4.50, 'Meat delivery'),
(11, 'PURCHASE', 200, 0.45, 'Monthly dry goods order'),
(1, 'USAGE', -5, NULL, 'Used in pico de gallo production'),
(6, 'USAGE', -10, NULL, 'Used in taco production');
