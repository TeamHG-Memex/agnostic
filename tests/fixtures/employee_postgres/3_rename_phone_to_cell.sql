/*
 * Rename the phone field to phone_cell.
 *
 * This intentionally conflicts with 2_rename_phone_to_home.sql!
 */

ALTER TABLE employee RENAME phone TO phone_cell;
