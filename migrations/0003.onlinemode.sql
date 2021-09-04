ALTER TABLE users
ADD COLUMN online INTEGER NULL;

update users
set online = 1;
