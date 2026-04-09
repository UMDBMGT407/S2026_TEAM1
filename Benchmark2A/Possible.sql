CREATE DATABASE IF NOT EXISTS kft_inventory;
USE kft_inventory;

-- Drop tables in dependency order
DROP TABLE IF EXISTS drink_product;
DROP TABLE IF EXISTS pos_transactions;
DROP TABLE IF EXISTS order_predictions;
DROP TABLE IF EXISTS purchase_order_items;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS inventory_updates;
DROP TABLE IF EXISTS audit_items;
DROP TABLE IF EXISTS audits;
DROP TABLE IF EXISTS drinks;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS users;

-- =========================
-- USERS
-- =========================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('Manager', 'ShiftLead', 'Employee') NOT NULL,
    phone VARCHAR(15),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =========================
-- INVENTORY ITEMS
-- Single master list for all ingredients / stock items
-- =========================
CREATE TABLE inventory_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    system_qty INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =========================
-- DRINKS
-- Finished menu items
-- =========================
CREATE TABLE drinks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    drink_name VARCHAR(150) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- =========================
-- AUDITS
-- =========================
CREATE TABLE audits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conducted_by INT NOT NULL,
    approved_by INT NULL,
    status ENUM('Draft', 'Submitted', 'Approved') NOT NULL DEFAULT 'Draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at DATETIME NULL,
    approved_at DATETIME NULL,
    CONSTRAINT fk_audits_conducted_by
        FOREIGN KEY (conducted_by) REFERENCES users(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_audits_approved_by
        FOREIGN KEY (approved_by) REFERENCES users(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- =========================
-- AUDIT ITEMS
-- Snapshot of each inventory item during an audit
-- =========================
CREATE TABLE audit_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    audit_id INT NOT NULL,
    inventory_item_id INT NOT NULL,
    system_qty INT NOT NULL,
    physical_count INT NOT NULL,
    CONSTRAINT fk_audit_items_audit
        FOREIGN KEY (audit_id) REFERENCES audits(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_audit_items_inventory
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT uq_audit_item UNIQUE (audit_id, inventory_item_id)
) ENGINE=InnoDB;

-- =========================
-- INVENTORY UPDATES / ACTIVITY LOG
-- =========================
CREATE TABLE inventory_updates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventory_item_id INT NOT NULL,
    updated_by INT NOT NULL,
    action_type ENUM('Add', 'Sub', 'Correct') NOT NULL,
    qty_change INT NOT NULL,
    old_qty INT NOT NULL,
    new_qty INT NOT NULL,
    audit_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inventory_updates_inventory
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_updates_user
        FOREIGN KEY (updated_by) REFERENCES users(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_updates_audit
        FOREIGN KEY (audit_id) REFERENCES audits(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- =========================
-- SUPPLIERS
-- =========================
CREATE TABLE suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name VARCHAR(100) NOT NULL,
    supplier_address VARCHAR(255)
) ENGINE=InnoDB;

-- =========================
-- PURCHASE ORDERS
-- Header table
-- =========================
CREATE TABLE purchase_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id INT NOT NULL,
    order_date DATE NOT NULL,
    expected_date DATE,
    received_date DATE,
    order_status ENUM('Pending', 'Ordered', 'Received', 'Cancelled') DEFAULT 'Pending',
    CONSTRAINT fk_purchase_orders_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================
-- PURCHASE ORDER ITEMS
-- Each order can have multiple inventory items
-- =========================
CREATE TABLE purchase_order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    purchase_order_id INT NOT NULL,
    inventory_item_id INT NOT NULL,
    quantity INT NOT NULL,
    CONSTRAINT fk_purchase_order_items_order
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_purchase_order_items_inventory
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================
-- ORDER PREDICTIONS
-- Predicted reorder amounts for inventory items
-- =========================
CREATE TABLE order_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventory_item_id INT NOT NULL,
    prediction_quantity INT NOT NULL,
    prediction_order_by_date DATE NOT NULL,
    prediction_date_created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_order_predictions_inventory
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================
-- POS TRANSACTIONS
-- Sales transactions for drinks
-- =========================
CREATE TABLE pos_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_date DATETIME NOT NULL,
    transaction_amount DECIMAL(10,2) NOT NULL,
    drink_id INT NOT NULL,
    CONSTRAINT fk_pos_transactions_drink
        FOREIGN KEY (drink_id) REFERENCES drinks(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================
-- DRINK_PRODUCT
-- Recipe / mapping table:
-- which inventory items are used in each drink
-- =========================
CREATE TABLE drink_product (
    drink_id INT NOT NULL,
    inventory_item_id INT NOT NULL,
    PRIMARY KEY (drink_id, inventory_item_id),
    CONSTRAINT fk_drink_product_drink
        FOREIGN KEY (drink_id) REFERENCES drinks(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_drink_product_inventory
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- =========================
-- USERS DATA
-- =========================
INSERT INTO users (name, email, password, role, phone) VALUES
(
    'Evelyn',
    'manager@kft.com',
    'scrypt:32768:8:1$v1WOHXvAJEtwb8ee$a9a95fa9fc242c08aa9c06b859aedacb9056a4720abf20278975af6ac21b71009e89d8af6b556e8ab78e810b74e62eb80d8d40f6a9afb0a44fbd31233e693a56',
    'Manager',
    '3015551023'
),
(
    'Felicia',
    'shiftlead@kft.com',
    'scrypt:32768:8:1$GeoWmBfnECIAgVPu$1997ef23573886aa4a0c7bc8c1d94745ed9144c6a45f8d3b091b83d5d7a40cfa1f47f05e33685a40bd6d8827205a25046f71936032c100205251a6a65413a9cd',
    'ShiftLead',
    '2405557845'
),
(
    'Sophie',
    'employee@kft.com',
    'scrypt:32768:8:1$okMNs94htS1V0A8d$72f9e291df301d503b3e19695d3530449ec4058db434c631f69651b6a2443ab726edd6fce54660ad1c940b8e605e6dfaffd8334b3673a8d6424b325bb1019f92',
    'Employee',
    '2025553399'
);

-- =========================
-- INVENTORY ITEMS DATA
-- Includes current inventory + orderable items
-- =========================
INSERT INTO inventory_items (item_name, category, system_qty) VALUES
('Tapioca Pearls', 'Toppings', 10),
('Black Tea', 'Tea', 6),
('Mango Syrup', 'Syrup', 5),
('Large Cups', 'Packaging', 20),
('Milk Powder', 'Powder', 8),
('Brown Sugar', 'Powder', 4),
('Hot Medium Cups', 'Packaging', 14),
('Matcha Powder', 'Powder', 3),
('Aloe Vera', 'Toppings', 0),
('Assam Black Tea Leaves', 'Tea', 0),
('Black Sugar Syrup', 'Syrup', 0),
('Brown Sugar Syrup', 'Syrup', 0),
('Bubble Tea Cups (Large)', 'Packaging', 0),
('Bubble Tea Cups (Medium)', 'Packaging', 0),
('Bubble Tea Lids', 'Packaging', 0),
('Bubble Tea Straws', 'Packaging', 0),
('Cane Sugar', 'Sweetener', 0),
('Cheese Milk Foam Powder', 'Powder', 0),
('Cheese Milk Foam Premix', 'Powder', 0),
('Chia Seeds', 'Toppings', 0),
('Coconut Jelly', 'Toppings', 0),
('Coffee Jelly', 'Toppings', 0),
('Creamer Powder', 'Powder', 0),
('Crystal Boba', 'Toppings', 0),
('Earl Grey Tea Leaves', 'Tea', 0),
('Fresh Milk (Whole)', 'Dairy', 0),
('Fruit Jam - Grape', 'Jam', 0),
('Fruit Jam - Mango', 'Jam', 0),
('Fruit Jam - Passion Fruit', 'Jam', 0),
('Fruit Jam - Peach', 'Jam', 0),
('Fruit Jam - Strawberry', 'Jam', 0),
('Grass Jelly', 'Toppings', 0),
('Green Tea Leaves', 'Tea', 0),
('Honey', 'Sweetener', 0),
('Ice (Bagged)', 'Other', 0),
('Jasmine Green Tea Leaves', 'Tea', 0),
('Lychee Jelly', 'Toppings', 0),
('Milk Powder (Non-Dairy)', 'Powder', 0),
('Oolong Tea Leaves', 'Tea', 0),
('Oreo Crumble', 'Toppings', 0),
('Passion Fruit Syrup', 'Syrup', 0),
('Pineapple Syrup', 'Syrup', 0),
('Pudding Mix', 'Powder', 0),
('Red Bean', 'Toppings', 0),
('Roasted Oolong Tea Leaves', 'Tea', 0),
('Salted Cream Foam Powder', 'Powder', 0),
('Simple Syrup', 'Syrup', 0),
('Thai Tea Leaves', 'Tea', 0),
('Tapioca Pearls (Boba)', 'Toppings', 0),
('Tiramisu Powder', 'Powder', 0),
('Wintermelon Syrup', 'Syrup', 0),
('Yakult', 'Dairy', 0);

-- =========================
-- DRINKS DATA
-- =========================
INSERT INTO drinks (drink_name) VALUES
('Winter Melon Milk Tea'),
('Brown Sugar Boba Latte');

-- =========================
-- SUPPLIER DATA
-- =========================
INSERT INTO suppliers (supplier_name, supplier_address)
VALUES ('Kung Fu Tea HQ', '589 8th Ave, 17th Floor, New York, NY 10018');

-- =========================
-- SAMPLE APPROVED AUDIT
-- =========================
INSERT INTO audits (conducted_by, approved_by, status, created_at, submitted_at, approved_at)
VALUES (2, 1, 'Approved', NOW(), NOW(), NOW());

SET @approved_audit_id = LAST_INSERT_ID();

INSERT INTO audit_items (audit_id, inventory_item_id, system_qty, physical_count)
SELECT
    @approved_audit_id,
    id,
    system_qty,
    system_qty
FROM inventory_items;

-- =========================
-- SAMPLE ACTIVITY LOG
-- =========================
INSERT INTO inventory_updates (inventory_item_id, updated_by, action_type, qty_change, old_qty, new_qty, audit_id)
VALUES
(
    (SELECT id FROM inventory_items WHERE item_name = 'Mango Syrup'),
    1,
    'Sub',
    -2,
    7,
    5,
    @approved_audit_id
),
(
    (SELECT id FROM inventory_items WHERE item_name = 'Large Cups'),
    1,
    'Add',
    3,
    17,
    20,
    @approved_audit_id
);

-- =========================
-- PURCHASE ORDERS DATA
-- =========================
INSERT INTO purchase_orders (supplier_id, order_date, expected_date, received_date, order_status) VALUES
(1, '2026-02-18', '2026-02-24', '2026-02-24', 'Received'),
(1, '2026-02-24', '2026-03-01', '2026-03-01', 'Received'),
(1, '2026-02-28', '2026-03-04', '2026-03-05', 'Received'),
(1, '2026-03-05', '2026-03-11', NULL, 'Pending');

-- =========================
-- PURCHASE ORDER ITEMS DATA
-- =========================

-- Order 1
INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 1, id, 6
FROM inventory_items
WHERE item_name = 'Lychee Jelly';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 1, id, 10
FROM inventory_items
WHERE item_name = 'Fresh Milk (Whole)';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 1, id, 5
FROM inventory_items
WHERE item_name = 'Oolong Tea Leaves';

-- Order 2
INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 2, id, 5
FROM inventory_items
WHERE item_name = 'Black Sugar Syrup';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 2, id, 5
FROM inventory_items
WHERE item_name = 'Green Tea Leaves';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 2, id, 4
FROM inventory_items
WHERE item_name = 'Bubble Tea Cups (Large)';

-- Order 3
INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 3, id, 5
FROM inventory_items
WHERE item_name = 'Chia Seeds';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 3, id, 10
FROM inventory_items
WHERE item_name = 'Milk Powder (Non-Dairy)';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 3, id, 4
FROM inventory_items
WHERE item_name = 'Bubble Tea Cups (Medium)';

-- Order 4
INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 4, id, 6
FROM inventory_items
WHERE item_name = 'Tiramisu Powder';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 4, id, 9
FROM inventory_items
WHERE item_name = 'Simple Syrup';

INSERT INTO purchase_order_items (purchase_order_id, inventory_item_id, quantity)
SELECT 4, id, 8
FROM inventory_items
WHERE item_name = 'Matcha Powder';

-- =========================
-- ORDER PREDICTIONS DATA
-- =========================
INSERT INTO order_predictions (
    inventory_item_id,
    prediction_quantity,
    prediction_order_by_date,
    prediction_date_created
) VALUES
(
    (SELECT id FROM inventory_items WHERE item_name = 'Tapioca Pearls'),
    64,
    '2026-04-09',
    '2026-04-08 09:00:00'
),
(
    (SELECT id FROM inventory_items WHERE item_name = 'Black Tea'),
    30,
    '2026-04-10',
    '2026-04-08 09:30:00'
);

-- =========================
-- POS TRANSACTIONS DATA
-- =========================
INSERT INTO pos_transactions (
    transaction_date,
    transaction_amount,
    drink_id
) VALUES
(
    '2026-04-08 10:15:00',
    6.75,
    (SELECT id FROM drinks WHERE drink_name = 'Winter Melon Milk Tea')
),
(
    '2026-04-08 14:40:00',
    7.25,
    (SELECT id FROM drinks WHERE drink_name = 'Brown Sugar Boba Latte')
);

-- =========================
-- DRINK / PRODUCT MAPPING DATA
-- =========================
INSERT INTO drink_product (drink_id, inventory_item_id) VALUES
(
    (SELECT id FROM drinks WHERE drink_name = 'Winter Melon Milk Tea'),
    (SELECT id FROM inventory_items WHERE item_name = 'Black Tea')
),
(
    (SELECT id FROM drinks WHERE drink_name = 'Winter Melon Milk Tea'),
    (SELECT id FROM inventory_items WHERE item_name = 'Wintermelon Syrup')
),
(
    (SELECT id FROM drinks WHERE drink_name = 'Brown Sugar Boba Latte'),
    (SELECT id FROM inventory_items WHERE item_name = 'Tapioca Pearls')
),
(
    (SELECT id FROM drinks WHERE drink_name = 'Brown Sugar Boba Latte'),
    (SELECT id FROM inventory_items WHERE item_name = 'Brown Sugar Syrup')
);

-- =========================
-- CHECK DATA
-- =========================
SELECT * FROM users;
SELECT * FROM inventory_items;
SELECT * FROM drinks;
SELECT * FROM audits;
SELECT * FROM audit_items;
SELECT * FROM inventory_updates;
SELECT * FROM suppliers;
SELECT * FROM purchase_orders;
SELECT * FROM purchase_order_items;
SELECT * FROM order_predictions;
SELECT * FROM pos_transactions;
SELECT * FROM drink_product;
