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
