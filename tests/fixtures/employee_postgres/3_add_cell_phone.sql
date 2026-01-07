/*
 * Add a new cell phone column.
 *
 * This resolves the conflict between 2_rename_phone_to_home.sql and
 * 3_rename_phone_to_cell.sql.
 */

ALTER TABLE employee ADD phone_cell VARCHAR(10);
