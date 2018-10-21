/*
 * Rename the existing phone field to phone_home.
 *
 * This intentionally conflicts with 3_rename_phone_to_cell.sql!
 *
 * SQLite doesn't support renaming columns, so we have to create a whole new
 * table!
 */

ALTER TABLE employee RENAME TO employee_backup;
CREATE TABLE employee (
    id INT PRIMARY KEY,
    name_first VARCHAR(100),
    name_last VARCHAR(100),
    phone_home VARCHAR(10)
);
INSERT INTO employee SELECT * FROM employee_backup;
DROP TABLE employee_backup;
