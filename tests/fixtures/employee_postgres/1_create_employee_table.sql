/*
 * Create an employee table.
 */

CREATE TABLE employee (
    id INT PRIMARY KEY,
    name_first VARCHAR(100),
    name_last VARCHAR(100),
    phone VARCHAR(10)
);

/* Make sure that multiple statements in a single file are supported. */

CREATE TABLE compensation (
    id INT PRIMARY KEY,
    salary INT NOT NULL,
    employee_id INT NOT NULL
);

/* Make sure that types are created/dropped correctly. */

CREATE TYPE emp_type AS ENUM ('fulltime', 'partime', 'freelance');

/* Make sure that sequences are created/dropped correctly. */

CREATE SEQUENCE emp_id START 1 INCREMENT 1;
