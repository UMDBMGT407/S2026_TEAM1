CREATE DATABASE IF NOT EXISTS kft_inventory;
USE kft_inventory;

DROP TABLE IF EXISTS inventory_updates;
DROP TABLE IF EXISTS audit_items;
DROP TABLE IF EXISTS audits;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS users;

-- USERS
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('Manager', 'ShiftLead', 'Employee') NOT NULL,
    phone VARCHAR(15),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVENTORY ITEMS
CREATE TABLE inventory_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    system_qty INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AUDITS
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
);

-- AUDIT ITEMS
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
);

-- ACTIVITY LOG
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
);

-- USERS
INSERT INTO users (name, email, password, role, phone_number) VALUES
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

-- INVENTORY
INSERT INTO inventory_items (item_name, category, system_qty) VALUES
('Tapioca Pearls', 'Toppings', 10),
('Black Tea', 'Tea', 6),
('Mango Syrup', 'Syrup', 5),
('Large Cups', 'Packaging', 20),
('Milk Powder', 'Powder', 8),
('Brown Sugar', 'Powder', 4),
('Hot Medium Cups', 'Packaging', 14),
('Matcha Powder', 'Powder', 3);

-- SAMPLE APPROVED AUDIT
INSERT INTO audits (conducted_by, approved_by, status, created_at, submitted_at, approved_at)
VALUES
(2, 1, 'Approved', NOW(), NOW(), NOW());

SET @approved_audit_id = LAST_INSERT_ID();

INSERT INTO audit_items (audit_id, inventory_item_id, system_qty, physical_count)
SELECT
    @approved_audit_id,
    id,
    system_qty,
    system_qty
FROM inventory_items;

-- SAMPLE ACTIVITY
INSERT INTO inventory_updates (inventory_item_id, updated_by, action_type, qty_change, old_qty, new_qty, audit_id)
VALUES
(3, 1, 'Sub', -2, 7, 5, @approved_audit_id),
(4, 1, 'Add', 3, 17, 20, @approved_audit_id);

SELECT * FROM users;
SELECT * FROM inventory_items;
SELECT * FROM audits;
SELECT * FROM audit_items;
SELECT * FROM inventory_updates;

-- *PURCHASE ORDERS* --
CREATE DATABASE kft_inventory_management;

USE kft_inventory_management;

CREATE TABLE Suppliers (
    supplierID INT PRIMARY KEY AUTO_INCREMENT,
    supplierName VARCHAR(100) NOT NULL,
    supplierAddress VARCHAR(255)
);

CREATE TABLE purchaseOrders (
	orderID INT PRIMARY KEY AUTO_INCREMENT,
    supplierID INT,
    orderDate DATE NOT NULL,
    expectedDate DATE,
    receivedDate DATE,
    orderStatus VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (supplierID) REFERENCES Suppliers(supplierID)
);

CREATE TABLE Products (
	productID INT PRIMARY KEY AUTO_INCREMENT,
    productName VARCHAR(100) NOT NULL
);

CREATE TABLE orderItems (
	orderItemID INT PRIMARY KEY AUTO_INCREMENT,
    orderID INT,
    productID INT,
    quantity INT NOT NULL,
    FOREIGN KEY (orderID) REFERENCES PurchaseOrders(orderID),
    FOREIGN KEY (productID) REFERENCES Products(productID)
);

INSERT INTO Suppliers (supplierID, supplierName, supplierAddress)
VALUES ('1', 'Kung Fu Tea HQ', '589 8th Ave, 17th Floor, New York, NY 10018');

INSERT INTO Products (productID, productName) VALUES
(1, 'Aloe Vera'),
(2, 'Assam Black Tea Leaves'),
(3, 'Black Sugar Syrup'),
(4, 'Brown Sugar Syrup'),
(5, 'Bubble Tea Cups (Large)'),
(6, 'Bubble Tea Cups (Medium)'),
(7, 'Bubble Tea Lids'),
(8, 'Bubble Tea Straws'),
(9, 'Cane Sugar'),
(10, 'Cheese Milk Foam Powder'),
(11, 'Cheese Milk Foam Premix'),
(12, 'Chia Seeds'),
(13, 'Coconut Jelly'),
(14, 'Coffee Jelly'),
(15, 'Creamer Powder'),
(16, 'Crystal Boba'),
(17, 'Earl Grey Tea Leaves'),
(18, 'Fresh Milk (Whole)'),
(19, 'Fruit Jam – Grape'),
(20, 'Fruit Jam – Mango'),
(21, 'Fruit Jam – Passion Fruit'),
(22, 'Fruit Jam – Peach'),
(23, 'Fruit Jam – Strawberry'),
(24, 'Grass Jelly'),
(25, 'Green Tea Leaves'),
(26, 'Honey'),
(27, 'Ice (Bagged)'),
(28, 'Jasmine Green Tea Leaves'),
(29, 'Lychee Jelly'),
(30, 'Matcha Powder'),
(31, 'Milk Powder (Non-Dairy)'),
(32, 'Oolong Tea Leaves'),
(33, 'Oreo Crumble'),
(34, 'Passion Fruit Syrup'),
(35, 'Pineapple Syrup'),
(36, 'Pudding Mix'),
(37, 'Red Bean'),
(38, 'Roasted Oolong Tea Leaves'),
(39, 'Salted Cream Foam Powder'),
(40, 'Simple Syrup'),
(41, 'Tapioca Pearls (Boba)'),
(42, 'Thai Tea Leaves'),
(43, 'Tiramisu Powder'),
(44, 'Wintermelon Syrup'),
(45, 'Yakult');

INSERT INTO purchaseOrders (orderID, supplierID, orderDate, expectedDate, receivedDate, orderStatus) VALUES
(1, 1, '2026-02-18', '2026-02-24', '2026-02-24', 'Received'),
(2, 1, '2026-02-24', '2026-03-01', '2026-03-01', 'Received'),
(3, 1, '2026-02-28', '2026-03-04', '2026-03-05', 'Received'),
(4, 1, '2026-03-05', '2026-03-11', NULL, 'Pending');

-- orderItems
-- order 1
INSERT INTO orderItems (orderID, productID, quantity)
SELECT 1, productID, 6 FROM Products WHERE productName = 'Lychee Jelly';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 1, productID, 10 FROM Products WHERE productName = 'Fresh Milk (Whole';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 1, productID, 5 FROM Products WHERE productName = 'Oolong Tea Leaves';


-- PO2
INSERT INTO orderItems (orderID, productID, quantity)
SELECT 2, productID, 5 FROM Products WHERE productName = 'Black Sugar Syrup';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 2, productID, 5 FROM Products WHERE productName = 'Green Tea Leaves';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 2, productID, 4 FROM Products WHERE productName = 'Bubble Tea Cups (Large)';


-- PO3
INSERT INTO orderItems (orderID, productID, quantity)
SELECT 3, productID, 5 FROM Products WHERE productName = 'Chia Seeds';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 3, productID, 10 FROM Products WHERE productName = 'Milk Powder (Non-Dairy)';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 3, productID, 4 FROM Products WHERE productName = 'Bubble Tea Cups (Medium)';


-- PO4
INSERT INTO orderItems (orderID, productID, quantity)
SELECT 4, productID, 6 FROM Products WHERE productName = 'Tiramisu Powder';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 4, productID, 9 FROM Products WHERE productName = 'Simple Syrup';

INSERT INTO orderItems (orderID, productID, quantity)
SELECT 4, productID, 8 FROM Products WHERE productName = 'Matcha Powder';

SELECT * FROM Products;

SELECT * FROM Suppliers;

SELECT * FROM purchaseOrders;

