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
  `physical_count` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_audit_item` (`audit_id`,`inventory_item_id`),
  KEY `fk_audit_items_inventory` (`inventory_item_id`),
  CONSTRAINT `fk_audit_items_audit` FOREIGN KEY (`audit_id`) REFERENCES `audits` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_audit_items_inventory` FOREIGN KEY (`inventory_item_id`) REFERENCES `inventory_items` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=64 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_items`
--

LOCK TABLES `audit_items` WRITE;
/*!40000 ALTER TABLE `audit_items` DISABLE KEYS */;
INSERT INTO `audit_items` VALUES (1,1,1,10,10),(2,1,2,6,6),(3,1,3,5,5),(4,1,4,20,20),(5,1,5,8,8),(6,1,6,4,4),(7,1,7,14,14),(8,1,8,3,3),(9,1,9,2,2),(10,1,10,1,1),(11,1,11,6,6),(12,1,12,3,3),(13,1,13,4,4),(14,1,14,0,0),(15,1,15,0,0),(16,1,16,0,0),(17,1,17,0,0),(18,1,18,0,0),(19,1,19,0,0),(20,1,20,0,0),(21,1,21,0,0),(22,1,22,0,0),(23,1,23,0,0),(24,1,24,0,0),(25,1,25,0,0),(26,1,26,0,0),(27,1,27,0,0),(28,1,28,0,0),(29,1,29,0,0),(30,1,30,0,0),(31,1,31,0,0),(32,1,32,0,0),(33,1,33,0,0),(34,1,34,0,0),(35,1,35,0,0),(36,1,36,0,0),(37,1,37,0,0),(38,1,38,0,0),(39,1,39,0,0),(40,1,40,0,0),(41,1,41,0,0),(42,1,42,0,0),(43,1,43,0,0),(44,1,44,0,0),(45,1,45,0,0),(46,1,46,0,0),(47,1,47,0,0),(48,1,48,0,0),(49,1,49,0,0),(50,1,50,0,0),(51,1,51,0,0),(52,1,52,0,0);
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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audits`
--

LOCK TABLES `audits` WRITE;
/*!40000 ALTER TABLE `audits` DISABLE KEYS */;
INSERT INTO `audits` VALUES (1,2,1,'Approved','2026-04-16 03:45:36','2026-04-15 23:45:36','2026-04-15 23:45:36');
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
  KEY `fk_delivery_audits_po` (`purchase_order_id`),
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
INSERT INTO `drink_product` VALUES (1,2,1),(1,51,1),(2,1,1),(2,12,1);
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `drinks`
--

LOCK TABLES `drinks` WRITE;
/*!40000 ALTER TABLE `drinks` DISABLE KEYS */;
INSERT INTO `drinks` VALUES (2,'Brown Sugar Boba Latte'),(1,'Winter Melon Milk Tea');
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
  PRIMARY KEY (`id`),
  UNIQUE KEY `item_name` (`item_name`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inventory_items`
--

LOCK TABLES `inventory_items` WRITE;
/*!40000 ALTER TABLE `inventory_items` DISABLE KEYS */;
INSERT INTO `inventory_items` VALUES (1,'Tapioca Pearls','Toppings',10,'2026-04-16 03:45:36'),(2,'Black Tea','Tea',6,'2026-04-16 03:45:36'),(3,'Mango Syrup','Syrup',5,'2026-04-16 03:45:36'),(4,'Large Cups','Packaging',20,'2026-04-16 03:45:36'),(5,'Milk Powder','Powder',8,'2026-04-16 03:45:36'),(6,'Brown Sugar','Powder',4,'2026-04-16 03:45:36'),(7,'Hot Medium Cups','Packaging',14,'2026-04-16 03:45:36'),(8,'Matcha Powder','Powder',3,'2026-04-16 03:45:36'),(9,'Aloe Vera','Toppings',2,'2026-04-16 03:45:36'),(10,'Assam Black Tea Leaves','Tea',1,'2026-04-16 03:45:36'),(11,'Black Sugar Syrup','Syrup',6,'2026-04-16 03:45:36'),(12,'Brown Sugar Syrup','Syrup',3,'2026-04-16 03:45:36'),(13,'Bubble Tea Cups (Large)','Packaging',4,'2026-04-16 03:45:36'),(14,'Bubble Tea Cups (Medium)','Packaging',0,'2026-04-16 03:45:36'),(15,'Bubble Tea Lids','Packaging',0,'2026-04-16 03:45:36'),(16,'Bubble Tea Straws','Packaging',0,'2026-04-16 03:45:36'),(17,'Cane Sugar','Sweetener',0,'2026-04-16 03:45:36'),(18,'Cheese Milk Foam Powder','Powder',0,'2026-04-16 03:45:36'),(19,'Cheese Milk Foam Premix','Powder',0,'2026-04-16 03:45:36'),(20,'Chia Seeds','Toppings',0,'2026-04-16 03:45:36'),(21,'Coconut Jelly','Toppings',0,'2026-04-16 03:45:36'),(22,'Coffee Jelly','Toppings',0,'2026-04-16 03:45:36'),(23,'Creamer Powder','Powder',0,'2026-04-16 03:45:36'),(24,'Crystal Boba','Toppings',0,'2026-04-16 03:45:36'),(25,'Earl Grey Tea Leaves','Tea',0,'2026-04-16 03:45:36'),(26,'Fresh Milk (Whole)','Dairy',0,'2026-04-16 03:45:36'),(27,'Fruit Jam - Grape','Jam',0,'2026-04-16 03:45:36'),(28,'Fruit Jam - Mango','Jam',0,'2026-04-16 03:45:36'),(29,'Fruit Jam - Passion Fruit','Jam',0,'2026-04-16 03:45:36'),(30,'Fruit Jam - Peach','Jam',0,'2026-04-16 03:45:36'),(31,'Fruit Jam - Strawberry','Jam',0,'2026-04-16 03:45:36'),(32,'Grass Jelly','Toppings',0,'2026-04-16 03:45:36'),(33,'Green Tea Leaves','Tea',0,'2026-04-16 03:45:36'),(34,'Honey','Sweetener',0,'2026-04-16 03:45:36'),(35,'Ice (Bagged)','Other',0,'2026-04-16 03:45:36'),(36,'Jasmine Green Tea Leaves','Tea',0,'2026-04-16 03:45:36'),(37,'Lychee Jelly','Toppings',0,'2026-04-16 03:45:36'),(38,'Milk Powder (Non-Dairy)','Powder',0,'2026-04-16 03:45:36'),(39,'Oolong Tea Leaves','Tea',0,'2026-04-16 03:45:36'),(40,'Oreo Crumble','Toppings',0,'2026-04-16 03:45:36'),(41,'Passion Fruit Syrup','Syrup',0,'2026-04-16 03:45:36'),(42,'Pineapple Syrup','Syrup',0,'2026-04-16 03:45:36'),(43,'Pudding Mix','Powder',0,'2026-04-16 03:45:36'),(44,'Red Bean','Toppings',0,'2026-04-16 03:45:36'),(45,'Roasted Oolong Tea Leaves','Tea',0,'2026-04-16 03:45:36'),(46,'Salted Cream Foam Powder','Powder',0,'2026-04-16 03:45:36'),(47,'Simple Syrup','Syrup',0,'2026-04-16 03:45:36'),(48,'Thai Tea Leaves','Tea',0,'2026-04-16 03:45:36'),(49,'Tapioca Pearls (Boba)','Toppings',0,'2026-04-16 03:45:36'),(50,'Tiramisu Powder','Powder',0,'2026-04-16 03:45:36'),(51,'Wintermelon Syrup','Syrup',0,'2026-04-16 03:45:36'),(52,'Yakult','Dairy',0,'2026-04-16 03:45:36');
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
  `action_type` enum('Add','Sub','Correct','Receive','Audit') NOT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inventory_updates`
--

LOCK TABLES `inventory_updates` WRITE;
/*!40000 ALTER TABLE `inventory_updates` DISABLE KEYS */;
INSERT INTO `inventory_updates` VALUES (1,3,1,'Sub',-2,7,5,1,NULL,NULL,'2026-04-16 03:45:36'),(2,4,1,'Add',3,17,20,1,NULL,NULL,'2026-04-16 03:45:36');
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
-- Table structure for table `pos_transactions`
--

DROP TABLE IF EXISTS `pos_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pos_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `transaction_date` datetime NOT NULL,
  `transaction_amount` decimal(10,2) NOT NULL,
  `drink_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_pos_transactions_drink` (`drink_id`),
  CONSTRAINT `fk_pos_transactions_drink` FOREIGN KEY (`drink_id`) REFERENCES `drinks` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pos_transactions`
--

LOCK TABLES `pos_transactions` WRITE;
/*!40000 ALTER TABLE `pos_transactions` DISABLE KEYS */;
INSERT INTO `pos_transactions` VALUES (1,'2026-04-08 10:15:00',6.75,1),(2,'2026-04-08 14:40:00',7.25,2);
/*!40000 ALTER TABLE `pos_transactions` ENABLE KEYS */;
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
  `audit_status` VARCHAR(50) DEFAULT 'Pending',
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
INSERT INTO `purchase_orders` VALUES (1,1,'2026-02-18','2026-02-24','2026-02-24','Received'),(2,1,'2026-02-24','2026-03-01','2026-03-01','Received'),(3,1,'2026-02-28','2026-03-04','2026-03-05','Received'),(4,1,'2026-03-05','2026-03-11',NULL,'Pending');
/*!40000 ALTER TABLE `purchase_orders` ENABLE KEYS */;
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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `suppliers`
--

LOCK TABLES `suppliers` WRITE;
/*!40000 ALTER TABLE `suppliers` DISABLE KEYS */;
INSERT INTO `suppliers` VALUES (1,'Kung Fu Tea HQ','589 8th Ave, 17th Floor, New York, NY 10018');
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
INSERT INTO `users` VALUES (1,'Evelyn','manager@kft.com','scrypt:32768:8:1$v1WOHXvAJEtwb8ee$a9a95fa9fc242c08aa9c06b859aedacb9056a4720abf20278975af6ac21b71009e89d8af6b556e8ab78e810b74e62eb80d8d40f6a9afb0a44fbd31233e693a56','Manager','3015551023','2026-04-16 03:45:36'),(2,'Felicia','shiftlead@kft.com','scrypt:32768:8:1$GeoWmBfnECIAgVPu$1997ef23573886aa4a0c7bc8c1d94745ed9144c6a45f8d3b091b83d5d7a40cfa1f47f05e33685a40bd6d8827205a25046f71936032c100205251a6a65413a9cd','ShiftLead','2405557845','2026-04-16 03:45:36'),(3,'Sophie','employee@kft.com','scrypt:32768:8:1$okMNs94htS1V0A8d$72f9e291df301d503b3e19695d3530449ec4058db434c631f69651b6a2443ab726edd6fce54660ad1c940b8e605e6dfaffd8334b3673a8d6424b325bb1019f92','Employee','2025553399','2026-04-16 03:45:36');
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

-- Dump completed on 2026-04-15 23:49:50
