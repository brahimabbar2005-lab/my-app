-- Destination taglines per UI language (Milestone v0.2; Master Plan §47).
alter table public.destinations
  alter column tagline type jsonb
  using case when tagline is null then null else jsonb_build_object('en', tagline) end;
comment on column public.destinations.tagline is 'Short description per UI language: {"en","fr","ar","es"}';
