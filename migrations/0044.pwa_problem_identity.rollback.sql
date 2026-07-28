drop trigger problems_public_id_immutable;
drop trigger problems_public_id_fill_after_insert;
drop index problems_public_id_uq;
alter table problems drop column public_id;
