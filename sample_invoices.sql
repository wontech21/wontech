-- Sample Purchase Orders and Invoices

-- Sample Purchase Order
INSERT INTO purchase_orders (po_number, supplier_name, order_date, expected_delivery_date, status, notes)
VALUES ('PO-2024-001', 'Fresh Produce Wholesalers', '2024-01-08', '2024-01-10', 'RECEIVED', 'Weekly produce order');

INSERT INTO po_line_items (po_id, ingredient_code, ingredient_name, quantity_ordered, unit_of_measure, unit_price, total_price)
VALUES
(1, 'ING-TOM-001', 'Roma Tomatoes', 25, 'lbs', 2.50, 62.50),
(1, 'ING-ONI-001', 'Yellow Onions', 20, 'lbs', 1.25, 25.00),
(1, 'ING-LET-001', 'Iceberg Lettuce', 12, 'heads', 1.50, 18.00);

-- Sample Invoice #1 - Matches PO
INSERT INTO invoices (invoice_number, po_id, supplier_name, invoice_date, received_date, total_amount, payment_status, reconciled, notes)
VALUES ('INV-2024-001', 1, 'Fresh Produce Wholesalers', '2024-01-10', '2024-01-10', 105.50, 'UNPAID', 'NO', 'Weekly produce delivery');

INSERT INTO invoice_line_items (invoice_id, ingredient_code, ingredient_name, quantity_received, unit_of_measure, unit_price, total_price, lot_number, expiration_date)
VALUES
(1, 'ING-TOM-001', 'Roma Tomatoes', 25, 'lbs', 2.50, 62.50, 'LOT-TOM-20240110', '2024-01-17'),
(1, 'ING-ONI-001', 'Yellow Onions', 20, 'lbs', 1.25, 25.00, 'LOT-ONI-20240110', '2024-01-24'),
(1, 'ING-LET-001', 'Iceberg Lettuce', 12, 'heads', 1.50, 18.00, 'LOT-LET-20240110', '2024-01-15');

-- Sample Invoice #2 - No PO (direct purchase)
INSERT INTO invoices (invoice_number, po_id, supplier_name, invoice_date, received_date, total_amount, payment_status, reconciled, notes)
VALUES ('INV-2024-002', NULL, 'Sysco Foods', '2024-01-09', '2024-01-09', 487.50, 'UNPAID', 'NO', 'Emergency meat order');

INSERT INTO invoice_line_items (invoice_id, ingredient_code, ingredient_name, quantity_received, unit_of_measure, unit_price, total_price, lot_number, expiration_date)
VALUES
(2, 'ING-BEF-001', 'Ground Beef 80/20', 50, 'lbs', 4.50, 225.00, 'LOT-BEEF-20240109', '2024-01-16'),
(2, 'ING-CHK-001', 'Chicken Breast', 40, 'lbs', 3.25, 130.00, 'LOT-CHK-20240109', '2024-01-16'),
(2, 'ING-POR-001', 'Pulled Pork', 23, 'lbs', 5.75, 132.25, 'LOT-PORK-20240109', '2024-01-23');

-- Sample Invoice #3 - Partial delivery (already reconciled to show example)
INSERT INTO invoices (invoice_number, po_id, supplier_name, invoice_date, received_date, total_amount, payment_status, reconciled, reconciled_date, notes)
VALUES ('INV-2024-003', NULL, 'US Foods', '2024-01-05', '2024-01-05', 215.00, 'PAID', 'YES', '2024-01-05 14:30:00', 'Weekly dairy delivery');

INSERT INTO invoice_line_items (invoice_id, ingredient_code, ingredient_name, quantity_received, unit_of_measure, unit_price, total_price, lot_number, expiration_date, reconciled_to_inventory)
VALUES
(3, 'ING-CHE-001', 'Cheddar Cheese', 20, 'lbs', 5.25, 105.00, 'LOT-CHE-20240105', '2024-02-05', 'YES'),
(3, 'ING-TOR-001', 'Flour Tortillas (10-inch)', 20, 'dozen', 3.00, 60.00, 'LOT-TOR-20240105', '2024-01-19', 'YES'),
(3, 'ING-BUN-001', 'Burger Buns', 20, 'dozen', 2.50, 50.00, 'LOT-BUN-20240105', '2024-01-12', 'YES');

-- Log the reconciliation
INSERT INTO reconciliation_log (invoice_id, invoice_line_item_id, ingredient_code, quantity_added, reconciled_date, reconciled_by, notes)
VALUES
(3, 1, 'ING-CHE-001', 20, '2024-01-05 14:30:00', 'John Manager', 'Received and verified'),
(3, 2, 'ING-TOR-001', 20, '2024-01-05 14:30:00', 'John Manager', 'Received and verified'),
(3, 3, 'ING-BUN-001', 20, '2024-01-05 14:30:00', 'John Manager', 'Received and verified');
