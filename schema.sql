CREATE DATABASE IF NOT EXISTS cryptovision CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cryptovision;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  username VARCHAR(80) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS datasets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,
  original_filename VARCHAR(255) NOT NULL,
  file_type VARCHAR(20) NOT NULL,
  original_path VARCHAR(500) NOT NULL,
  row_count INT NOT NULL DEFAULT 0,
  column_count INT NOT NULL DEFAULT 0,
  cleaned_filename VARCHAR(255) NOT NULL,
  cleaned_path VARCHAR(500) NOT NULL,
  metadata_json TEXT NOT NULL,
  uploaded_at DATETIME NOT NULL,
  CONSTRAINT fk_datasets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  dataset_id INT NOT NULL,
  asset_name VARCHAR(255),
  model_type VARCHAR(80) NOT NULL,
  target_column VARCHAR(255) NOT NULL,
  date_column VARCHAR(255),
  metrics_json TEXT NOT NULL,
  prediction_file VARCHAR(500),
  created_at DATETIME NOT NULL,
  CONSTRAINT fk_predictions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_predictions_dataset FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);

