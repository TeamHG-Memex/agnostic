/*
 * Rename the existing phone field and add cell_phone field.
 *
 * This intentionally conflicts with 2_rename_phone_to_home.sql!
 *
 * SQLite doesn't support renaming columns, so we have to create a whole new
 * table!
 */

ALTER TABLE employee RENAME TO employee_backup;
CREATE TABLE employee (
    id INT PRIMARY KEY,
    name_first VARCHAR(100),
    name_last VARCHAR(100),
    phone_cell VARCHAR(10)
);
INSERT INTO employee SELECT * FROM employee_backup;
DROP TABLE employee_backup;
