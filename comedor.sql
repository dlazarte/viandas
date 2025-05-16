-- Migrations will appear here as you chat with AI

create table students (
  id bigint primary key generated always as identity,
  name text not null,
  grade text not null
);

create table menus (
  id bigint primary key generated always as identity,
  type text not null,
  description text
);

create table meals (
  id bigint primary key generated always as identity,
  student_id bigint references students (id),
  menu_id bigint references menus (id),
  date date not null
);

create table payments (
  id bigint primary key generated always as identity,
  student_id bigint references students (id),
  amount numeric(10, 2) not null,
  payment_date date not null
);

alter table students
add column is_enabled boolean default true,
add column guardian_name text,
add column guardian_contact text;

create table schools (
  id bigint primary key generated always as identity,
  name text not null,
  address text
);

alter table students
add column school_id bigint references schools (id);

alter table payments
add column school_id bigint references schools (id);

alter table meals
add column school_id bigint references schools (id);
