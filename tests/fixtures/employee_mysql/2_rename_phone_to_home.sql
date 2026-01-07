/*
 * Rename the existing phone field to phone_home.
 *
 * This intentionally conflicts with 3_rename_phone_to_cell.sql!
 */

ALTER TABLE employee CHANGE phone phone_home VARCHAR(10);
