-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: localhost    Database: kft_inventory
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `audit_items`
--

DROP TABLE IF EXISTS `audit_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `audit_id` int NOT NULL,
  `inventory_item_id` int NOT NULL,
  `system_qty` int NOT NULL,
  `physical_count` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_audit_item` (`audit_id`,`inventory_item_id`),
  KEY `fk_audit_items_inventory` (`inventory_item_id`),
  CONSTRAINT `fk_audit_items_audit` FOREIGN KEY (`audit_id`) REFERENCES `audits` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_audit_items_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_items`
--

LOCK TABLES `audit_items` WRITE;
/*!40000 ALTER TABLE `audit_items` DISABLE KEYS */;
INSERT INTO `audit_items` VALUES (1,10,1,35,32),(2,10,2,30,30),(3,10,3,10,8),(4,11,1,23,23),(5,11,4,150,145),(6,11,2,22,25),(7,12,5,16,16),(8,12,1,53,50),(9,12,3,0,2),(10,13,6,8,8),(11,13,2,7,5),(12,13,4,110,108),(13,14,1,33,30),(14,14,5,26,26),(15,14,7,9,7),(16,15,2,32,30),(17,15,4,90,85),(18,15,3,20,20),(19,16,1,23,20),(20,16,8,5,5);
/*!40000 ALTER TABLE `audit_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `audits`
--

DROP TABLE IF EXISTS `audits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audits` (
  `id` int NOT NULL AUTO_INCREMENT,
  `conducted_by` int NOT NULL,
  `approved_by` int DEFAULT NULL,
  `status` enum('Draft','Submitted','Approved') NOT NULL DEFAULT 'Draft',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `submitted_at` datetime DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_audits_conducted_by` (`conducted_by`),
  KEY `fk_audits_approved_by` (`approved_by`),
  CONSTRAINT `fk_audits_approved_by` FOREIGN KEY (`approved_by`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_audits_conducted_by` FOREIGN KEY (`conducted_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audits`
--

LOCK TABLES `audits` WRITE;
/*!40000 ALTER TABLE `audits` DISABLE KEYS */;
INSERT INTO `audits` VALUES (10,2,1,'Approved','2026-04-03 22:00:00','2026-04-03 18:30:00','2026-04-03 19:00:00'),(11,2,1,'Approved','2026-04-07 22:00:00','2026-04-07 18:30:00','2026-04-07 19:00:00'),(12,2,1,'Approved','2026-04-10 22:00:00','2026-04-10 18:30:00','2026-04-10 19:00:00'),(13,2,1,'Approved','2026-04-14 22:00:00','2026-04-14 18:30:00','2026-04-14 19:00:00'),(14,2,1,'Approved','2026-04-17 22:00:00','2026-04-17 18:30:00','2026-04-17 19:00:00'),(15,2,1,'Approved','2026-04-21 22:00:00','2026-04-21 18:30:00','2026-04-21 19:00:00'),(16,2,1,'Approved','2026-04-24 22:00:00','2026-04-24 18:30:00','2026-04-24 19:00:00'),(17,2,1,'Approved','2026-04-28 14:00:00','2026-04-28 10:30:00','2026-04-28 11:00:00');
/*!40000 ALTER TABLE `audits` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `delivery_audits`
--

DROP TABLE IF EXISTS `delivery_audits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `delivery_audits` (
  `id` int NOT NULL AUTO_INCREMENT,
  `purchase_order_id` int NOT NULL,
  `inventory_item_id` int NOT NULL,
  `quantity_ordered` int NOT NULL,
  `quantity_received` int NOT NULL,
  `received_by` int NOT NULL,
  `received_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `notes` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_delivery_audits_po_item` (`purchase_order_id`,`inventory_item_id`),
  KEY `fk_delivery_audits_inventory` (`inventory_item_id`),
  KEY `fk_delivery_audits_user` (`received_by`),
  CONSTRAINT `fk_delivery_audits_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_delivery_audits_po` FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_delivery_audits_user` FOREIGN KEY (`received_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `delivery_audits`
--

LOCK TABLES `delivery_audits` WRITE;
/*!40000 ALTER TABLE `delivery_audits` DISABLE KEYS */;
/*!40000 ALTER TABLE `delivery_audits` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `drink_product`
--

DROP TABLE IF EXISTS `drink_product`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `drink_product` (
  `drink_id` int NOT NULL,
  `inventory_item_id` int NOT NULL,
  `quantity` float DEFAULT '1',
  PRIMARY KEY (`drink_id`,`inventory_item_id`),
  KEY `fk_drink_product_inventory` (`inventory_item_id`),
  CONSTRAINT `fk_drink_product_drink` FOREIGN KEY (`drink_id`) REFERENCES `drinks` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_drink_product_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `drink_product`
--

LOCK TABLES `drink_product` WRITE;
/*!40000 ALTER TABLE `drink_product` DISABLE KEYS */;
INSERT INTO `drink_product` VALUES (1,5,0.045),(1,10,0.035),(1,14,1),(1,15,1),(1,16,1),(1,35,0.08),(1,47,0.02),(2,5,0.04),(2,14,1),(2,15,1),(2,16,1),(2,23,0.03),(2,35,0.08),(2,47,0.018),(3,14,1),(3,15,1),(3,16,1),(3,17,0.02),(3,23,0.04),(3,35,0.075),(3,48,0.04),(4,14,1),(4,15,1),(4,33,0.03),(4,34,0.025),(4,35,0.08),(5,14,1),(5,15,1),(5,29,0.018),(5,33,0.028),(5,35,0.085),(5,41,0.028),(6,3,0.04),(6,13,1),(6,15,1),(6,16,1),(6,28,0.03),(6,35,0.14),(7,5,0.03),(7,13,1),(7,15,1),(7,16,1),(7,26,0.08),(7,35,0.09),(7,40,0.035),(7,47,0.018),(8,13,1),(8,15,1),(8,23,0.025),(8,26,0.085),(8,35,0.09),(8,46,0.03),(8,47,0.02),(9,8,0.028),(9,14,1),(9,15,1),(9,18,0.028),(9,26,0.06),(9,35,0.075),(9,36,0.022),(10,13,1),(10,15,1),(10,16,1),(10,31,0.032),(10,35,0.09),(10,47,0.015);
/*!40000 ALTER TABLE `drink_product` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `drinks`
--

DROP TABLE IF EXISTS `drinks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `drinks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `drink_name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `drink_name` (`drink_name`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `drinks`
--

LOCK TABLES `drinks` WRITE;
/*!40000 ALTER TABLE `drinks` DISABLE KEYS */;
INSERT INTO `drinks` VALUES (8,'Cocoa Cream Wow'),(4,'Honey Green Tea'),(1,'Kung Fu Milk Tea'),(6,'Mango Slush'),(9,'Matcha Milk Cap'),(7,'Oreo Wow'),(5,'Passion Fruit Green Tea'),(10,'Strawberry Lemonade'),(2,'Taro Milk Tea'),(3,'Thai Milk Tea');
/*!40000 ALTER TABLE `drinks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inventory_items`
--

DROP TABLE IF EXISTS `inventory_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inventory_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `item_name` varchar(100) NOT NULL,
  `category` varchar(50) NOT NULL,
  `system_qty` int NOT NULL DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `status` enum('Active','Retired') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `item_name` (`item_name`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inventory_items`
--

LOCK TABLES `inventory_items` WRITE;
/*!40000 ALTER TABLE `inventory_items` DISABLE KEYS */;
INSERT INTO `inventory_items` VALUES (1,'Tapioca Pearls','Toppings',8,'2026-04-30 20:56:35','Active'),(2,'Black Tea','Tea',6,'2026-04-30 20:56:35','Active'),(3,'Mango Syrup','Syrup',4,'2026-04-30 20:56:35','Active'),(4,'Large Cups','Packaging',180,'2026-04-30 20:56:35','Active'),(5,'Milk Powder','Powder',7,'2026-04-30 20:56:35','Active'),(6,'Brown Sugar','Powder',5,'2026-04-30 20:56:35','Active'),(7,'Hot Medium Cups','Packaging',120,'2026-04-30 20:56:35','Active'),(8,'Matcha Powder','Powder',4,'2026-04-30 20:56:35','Active'),(9,'Aloe Vera','Toppings',3,'2026-04-30 20:56:35','Active'),(10,'Assam Black Tea Leaves','Tea',5,'2026-04-30 20:56:35','Active'),(11,'Black Sugar Syrup','Syrup',4,'2026-04-30 20:56:35','Active'),(12,'Brown Sugar Syrup','Syrup',5,'2026-04-30 20:56:35','Active'),(13,'Bubble Tea Cups (Large)','Packaging',240,'2026-04-30 20:56:35','Active'),(14,'Bubble Tea Cups (Medium)','Packaging',260,'2026-04-30 20:56:35','Active'),(15,'Bubble Tea Lids','Packaging',520,'2026-04-30 20:56:35','Active'),(16,'Bubble Tea Straws','Packaging',480,'2026-04-30 20:56:35','Active'),(17,'Cane Sugar','Sweetener',8,'2026-04-30 20:56:35','Active'),(18,'Cheese Milk Foam Powder','Powder',3,'2026-04-30 20:56:35','Active'),(19,'Cheese Milk Foam Premix','Powder',2,'2026-04-30 20:56:35','Active'),(20,'Chia Seeds','Toppings',3,'2026-04-30 20:56:35','Active'),(21,'Coconut Jelly','Toppings',4,'2026-04-30 20:56:35','Active'),(22,'Coffee Jelly','Toppings',3,'2026-04-30 20:56:35','Active'),(23,'Creamer Powder','Powder',6,'2026-04-30 20:56:35','Active'),(24,'Crystal Boba','Toppings',2,'2026-04-30 20:56:35','Active'),(25,'Earl Grey Tea Leaves','Tea',3,'2026-04-30 20:56:35','Active'),(26,'Fresh Milk (Whole)','Dairy',14,'2026-04-30 20:56:35','Active'),(27,'Fruit Jam - Grape','Jam',2,'2026-04-30 20:56:35','Active'),(28,'Fruit Jam - Mango','Jam',4,'2026-04-30 20:56:35','Active'),(29,'Fruit Jam - Passion Fruit','Jam',3,'2026-04-30 20:56:35','Active'),(30,'Fruit Jam - Peach','Jam',2,'2026-04-30 20:56:35','Active'),(31,'Fruit Jam - Strawberry','Jam',3,'2026-04-30 20:56:35','Active'),(32,'Grass Jelly','Toppings',3,'2026-04-30 20:56:35','Active'),(33,'Green Tea Leaves','Tea',5,'2026-04-30 20:56:35','Active'),(34,'Honey','Sweetener',4,'2026-04-30 20:56:35','Active'),(35,'Ice (Bagged)','Other',18,'2026-04-30 20:56:35','Active'),(36,'Jasmine Green Tea Leaves','Tea',4,'2026-04-30 20:56:35','Active'),(37,'Lychee Jelly','Toppings',3,'2026-04-30 20:56:35','Active'),(38,'Milk Powder (Non-Dairy)','Powder',6,'2026-04-30 20:56:35','Active'),(39,'Oolong Tea Leaves','Tea',4,'2026-04-30 20:56:35','Active'),(40,'Oreo Crumble','Toppings',2,'2026-04-30 20:56:35','Active'),(41,'Passion Fruit Syrup','Syrup',3,'2026-04-30 20:56:35','Active'),(42,'Pineapple Syrup','Syrup',2,'2026-04-30 20:56:35','Active'),(43,'Pudding Mix','Powder',3,'2026-04-30 20:56:35','Active'),(44,'Red Bean','Toppings',2,'2026-04-30 20:56:35','Active'),(45,'Roasted Oolong Tea Leaves','Tea',3,'2026-04-30 20:56:35','Active'),(46,'Salted Cream Foam Powder','Powder',3,'2026-04-30 20:56:35','Active'),(47,'Simple Syrup','Syrup',8,'2026-04-30 20:56:35','Active'),(48,'Thai Tea Leaves','Tea',4,'2026-04-30 20:56:35','Active'),(49,'Tapioca Pearls (Boba)','Toppings',5,'2026-04-30 20:56:35','Active'),(50,'Tiramisu Powder','Powder',2,'2026-04-30 20:56:35','Active'),(51,'Wintermelon Syrup','Syrup',4,'2026-04-30 20:56:35','Active'),(52,'Yakult','Dairy',24,'2026-04-30 20:56:35','Active');
/*!40000 ALTER TABLE `inventory_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inventory_updates`
--

DROP TABLE IF EXISTS `inventory_updates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inventory_updates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `inventory_item_id` int NOT NULL,
  `updated_by` int NOT NULL,
  `action_type` enum('Add','Sub','Correct','Audit','Restock') NOT NULL,
  `qty_change` int NOT NULL,
  `old_qty` int NOT NULL,
  `new_qty` int NOT NULL,
  `audit_id` int DEFAULT NULL,
  `purchase_order_id` int DEFAULT NULL,
  `reason` varchar(255) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_inventory_updates_inventory` (`inventory_item_id`),
  KEY `fk_inventory_updates_user` (`updated_by`),
  KEY `fk_inventory_updates_audit` (`audit_id`),
  KEY `fk_inventory_updates_po` (`purchase_order_id`),
  CONSTRAINT `fk_inventory_updates_audit` FOREIGN KEY (`audit_id`) REFERENCES `audits` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_inventory_updates_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_inventory_updates_po` FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_inventory_updates_user` FOREIGN KEY (`updated_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inventory_updates`
--

LOCK TABLES `inventory_updates` WRITE;
/*!40000 ALTER TABLE `inventory_updates` DISABLE KEYS */;
INSERT INTO `inventory_updates` VALUES (1,1,1,'Sub',-15,50,35,NULL,NULL,NULL,'2026-04-01 14:00:00'),(2,2,1,'Add',20,10,30,NULL,NULL,NULL,'2026-04-02 13:30:00'),(3,3,1,'Sub',-5,15,10,NULL,NULL,NULL,'2026-04-03 18:20:00'),(4,1,1,'Sub',-12,35,23,NULL,NULL,NULL,'2026-04-05 15:00:00'),(5,4,1,'Add',50,100,150,NULL,NULL,NULL,'2026-04-06 12:45:00'),(6,2,1,'Sub',-8,30,22,NULL,NULL,NULL,'2026-04-08 20:30:00'),(7,5,1,'Sub',-4,20,16,NULL,NULL,NULL,'2026-04-10 16:15:00'),(8,1,1,'Add',30,23,53,NULL,NULL,NULL,'2026-04-12 13:00:00'),(9,3,1,'Sub',-10,10,0,NULL,NULL,NULL,'2026-04-14 22:00:00'),(10,6,1,'Sub',-2,10,8,NULL,NULL,NULL,'2026-04-15 17:00:00'),(11,2,1,'Sub',-15,22,7,NULL,NULL,NULL,'2026-04-17 15:20:00'),(12,4,1,'Sub',-40,150,110,NULL,NULL,NULL,'2026-04-19 19:40:00'),(13,1,1,'Sub',-20,53,33,NULL,NULL,NULL,'2026-04-20 14:10:00'),(14,5,1,'Add',10,16,26,NULL,NULL,NULL,'2026-04-22 12:30:00'),(15,7,1,'Sub',-5,14,9,NULL,NULL,NULL,'2026-04-24 16:00:00'),(16,2,1,'Add',25,7,32,NULL,NULL,NULL,'2026-04-25 13:15:00'),(17,1,1,'Sub',-10,33,23,NULL,NULL,NULL,'2026-04-26 21:45:00'),(18,3,1,'Add',20,0,20,NULL,NULL,NULL,'2026-04-27 14:00:00'),(19,8,1,'Sub',-3,3,0,NULL,NULL,NULL,'2026-04-28 15:30:00'),(20,4,1,'Sub',-20,110,90,NULL,NULL,NULL,'2026-04-28 18:00:00');
/*!40000 ALTER TABLE `inventory_updates` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `order_predictions`
--

DROP TABLE IF EXISTS `order_predictions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_predictions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `inventory_item_id` int NOT NULL,
  `prediction_quantity` int NOT NULL,
  `prediction_order_by_date` date NOT NULL,
  `prediction_date_created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_order_predictions_inventory` (`inventory_item_id`),
  CONSTRAINT `fk_order_predictions_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `order_predictions`
--

LOCK TABLES `order_predictions` WRITE;
/*!40000 ALTER TABLE `order_predictions` DISABLE KEYS */;
INSERT INTO `order_predictions` VALUES (1,1,64,'2026-04-09','2026-04-08 09:00:00'),(2,2,30,'2026-04-10','2026-04-08 09:30:00');
/*!40000 ALTER TABLE `order_predictions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orderitems`
--

DROP TABLE IF EXISTS `orderitems`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orderitems` (
  `orderItemID` int NOT NULL AUTO_INCREMENT,
  `orderID` int DEFAULT NULL,
  `productID` int DEFAULT NULL,
  `quantity` int NOT NULL,
  PRIMARY KEY (`orderItemID`),
  KEY `orderID` (`orderID`),
  KEY `productID` (`productID`),
  CONSTRAINT `orderitems_ibfk_1` FOREIGN KEY (`orderID`) REFERENCES `purchaseorders` (`orderID`),
  CONSTRAINT `orderitems_ibfk_2` FOREIGN KEY (`productID`) REFERENCES `products` (`productID`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orderitems`
--

LOCK TABLES `orderitems` WRITE;
/*!40000 ALTER TABLE `orderitems` DISABLE KEYS */;
INSERT INTO `orderitems` VALUES (1,1,29,6),(2,1,32,5),(3,2,3,5),(4,2,25,5),(5,2,5,4),(6,3,12,5),(7,3,31,10),(8,3,6,4),(9,4,43,6),(10,4,40,9),(11,4,30,8);
/*!40000 ALTER TABLE `orderitems` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pos_transactions`
--

DROP TABLE IF EXISTS `pos_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pos_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `transaction_id` varchar(64) NOT NULL,
  `transaction_date` datetime NOT NULL,
  `transaction_amount` decimal(10,2) NOT NULL,
  `drink_id` int NOT NULL,
  `quantity` int NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `transaction_id` (`transaction_id`),
  KEY `fk_pos_transactions_drink` (`drink_id`),
  CONSTRAINT `fk_pos_transactions_drink` FOREIGN KEY (`drink_id`) REFERENCES `drinks` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pos_transactions`
--

LOCK TABLES `pos_transactions` WRITE;
/*!40000 ALTER TABLE `pos_transactions` DISABLE KEYS */;
INSERT INTO `pos_transactions` VALUES (1,'TXN-SEED-0001','2026-04-08 10:15:00',6.75,10,1),(2,'TXN-SEED-0002','2026-04-08 14:40:00',7.25,3,2);
/*!40000 ALTER TABLE `pos_transactions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `products`
--

DROP TABLE IF EXISTS `products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products` (
  `productID` int NOT NULL AUTO_INCREMENT,
  `productName` varchar(100) NOT NULL,
  PRIMARY KEY (`productID`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products`
--

LOCK TABLES `products` WRITE;
/*!40000 ALTER TABLE `products` DISABLE KEYS */;
INSERT INTO `products` VALUES (1,'Aloe Vera'),(2,'Assam Black Tea Leaves'),(3,'Black Sugar Syrup'),(4,'Brown Sugar Syrup'),(5,'Bubble Tea Cups (Large)'),(6,'Bubble Tea Cups (Medium)'),(7,'Bubble Tea Lids'),(8,'Bubble Tea Straws'),(9,'Cane Sugar'),(10,'Cheese Milk Foam Powder'),(11,'Cheese Milk Foam Premix'),(12,'Chia Seeds'),(13,'Coconut Jelly'),(14,'Coffee Jelly'),(15,'Creamer Powder'),(16,'Crystal Boba'),(17,'Earl Grey Tea Leaves'),(18,'Fresh Milk (Whole)'),(19,'Fruit Jam – Grape'),(20,'Fruit Jam – Mango'),(21,'Fruit Jam – Passion Fruit'),(22,'Fruit Jam – Peach'),(23,'Fruit Jam – Strawberry'),(24,'Grass Jelly'),(25,'Green Tea Leaves'),(26,'Honey'),(27,'Ice (Bagged)'),(28,'Jasmine Green Tea Leaves'),(29,'Lychee Jelly'),(30,'Matcha Powder'),(31,'Milk Powder (Non-Dairy)'),(32,'Oolong Tea Leaves'),(33,'Oreo Crumble'),(34,'Passion Fruit Syrup'),(35,'Pineapple Syrup'),(36,'Pudding Mix'),(37,'Red Bean'),(38,'Roasted Oolong Tea Leaves'),(39,'Salted Cream Foam Powder'),(40,'Simple Syrup'),(41,'Tapioca Pearls (Boba)'),(42,'Thai Tea Leaves'),(43,'Tiramisu Powder'),(44,'Wintermelon Syrup'),(45,'Yakult');
/*!40000 ALTER TABLE `products` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `purchase_order_items`
--

DROP TABLE IF EXISTS `purchase_order_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `purchase_order_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `purchase_order_id` int NOT NULL,
  `inventory_item_id` int NOT NULL,
  `quantity` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_purchase_order_items_order` (`purchase_order_id`),
  KEY `fk_purchase_order_items_inventory` (`inventory_item_id`),
  CONSTRAINT `fk_purchase_order_items_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_purchase_order_items_order` FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `purchase_order_items`
--

LOCK TABLES `purchase_order_items` WRITE;
/*!40000 ALTER TABLE `purchase_order_items` DISABLE KEYS */;
INSERT INTO `purchase_order_items` VALUES (1,1,37,6),(2,1,26,10),(3,1,39,5),(4,2,11,5),(5,2,33,5),(6,2,13,4),(7,3,20,5),(8,3,38,10),(9,3,14,4),(10,4,50,6),(11,4,47,9),(12,4,8,8);
/*!40000 ALTER TABLE `purchase_order_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `purchase_orders`
--

DROP TABLE IF EXISTS `purchase_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `purchase_orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `supplier_id` int NOT NULL,
  `order_date` date NOT NULL,
  `expected_date` date DEFAULT NULL,
  `received_date` date DEFAULT NULL,
  `order_status` enum('Pending','Ordered','Received','Cancelled') DEFAULT 'Pending',
  `audit_status` varchar(50) DEFAULT 'Pending',
  PRIMARY KEY (`id`),
  KEY `fk_purchase_orders_supplier` (`supplier_id`),
  CONSTRAINT `fk_purchase_orders_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `purchase_orders`
--

LOCK TABLES `purchase_orders` WRITE;
/*!40000 ALTER TABLE `purchase_orders` DISABLE KEYS */;
INSERT INTO `purchase_orders` VALUES (1,1,'2026-02-18','2026-02-24','2026-02-24','Received','Pending'),(2,1,'2026-02-24','2026-03-01','2026-03-01','Received','Pending'),(3,1,'2026-02-28','2026-03-04','2026-03-05','Received','Pending'),(4,1,'2026-03-05','2026-03-11',NULL,'Pending','Pending');
/*!40000 ALTER TABLE `purchase_orders` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `purchaseorders`
--

DROP TABLE IF EXISTS `purchaseorders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `purchaseorders` (
  `orderID` int NOT NULL AUTO_INCREMENT,
  `supplierID` int DEFAULT NULL,
  `orderDate` date NOT NULL,
  `expectedDate` date DEFAULT NULL,
  `receivedDate` date DEFAULT NULL,
  `orderStatus` varchar(50) DEFAULT 'Pending',
  PRIMARY KEY (`orderID`),
  KEY `supplierID` (`supplierID`),
  CONSTRAINT `purchaseorders_ibfk_1` FOREIGN KEY (`supplierID`) REFERENCES `suppliers` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `purchaseorders`
--

LOCK TABLES `purchaseorders` WRITE;
/*!40000 ALTER TABLE `purchaseorders` DISABLE KEYS */;
INSERT INTO `purchaseorders` VALUES (1,1,'2026-02-18','2026-02-24','2026-02-24','Received'),(2,1,'2026-02-24','2026-03-01','2026-03-01','Received'),(3,1,'2026-02-28','2026-03-04','2026-03-05','Received'),(4,1,'2026-03-05','2026-03-11',NULL,'Pending');
/*!40000 ALTER TABLE `purchaseorders` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `suppliers`
--

DROP TABLE IF EXISTS `suppliers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `suppliers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `supplier_name` varchar(100) NOT NULL,
  `supplier_address` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `suppliers`
--

LOCK TABLES `suppliers` WRITE;
/*!40000 ALTER TABLE `suppliers` DISABLE KEYS */;
INSERT INTO `suppliers` VALUES (1,'Kung Fu Tea HQ','589 8th Ave, 17th Floor, New York, NY 10018'),(6,'Kung Fu Tea HQ','589 8th Ave, 17th Floor, New York, NY 10018');
/*!40000 ALTER TABLE `suppliers` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('Manager','ShiftLead','Employee') NOT NULL,
  `phone` varchar(15) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'Evelyn','manager@kft.com','scrypt:32768:8:1$v1WOHXvAJEtwb8ee$a9a95fa9fc242c08aa9c06b859aedacb9056a4720abf20278975af6ac21b71009e89d8af6b556e8ab78e810b74e62eb80d8d40f6a9afb0a44fbd31233e693a56','Manager','3015551023','2026-04-30 20:56:35'),(2,'Felicia','shiftlead@kft.com','scrypt:32768:8:1$GeoWmBfnECIAgVPu$1997ef23573886aa4a0c7bc8c1d94745ed9144c6a45f8d3b091b83d5d7a40cfa1f47f05e33685a40bd6d8827205a25046f71936032c100205251a6a65413a9cd','ShiftLead','2405557845','2026-04-30 20:56:35'),(3,'Sophie','employee@kft.com','scrypt:32768:8:1$okMNs94htS1V0A8d$72f9e291df301d503b3e19695d3530449ec4058db434c631f69651b6a2443ab726edd6fce54660ad1c940b8e605e6dfaffd8334b3673a8d6424b325bb1019f92','Employee','2025553399','2026-04-30 20:56:35');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-30 16:58:30
