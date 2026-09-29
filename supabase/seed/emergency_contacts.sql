-- Emergency numbers are shown with their source and verification date. They
-- ship unverified (last_verified = null) and the app says so; an editor sets
-- last_verified after confirming each number (Master Plan §17).
insert into public.emergency_contacts (id, country, service, label, number, scope, source, last_verified) values
  ('ma-police', 'MA', 'police', 'Police', '19', 'Cities', 'Moroccan national emergency numbers', null),
  ('ma-gendarmerie', 'MA', 'gendarmerie', 'Royal Gendarmerie', '177', 'Rural areas & highways', 'Moroccan national emergency numbers', null),
  ('ma-ambulance-fire', 'MA', 'ambulance_fire', 'Ambulance & fire (Protection Civile)', '15', 'Nationwide', 'Moroccan national emergency numbers', null),
  ('ma-112', 'MA', 'mobile_emergency', 'Emergency from a mobile phone', '112', 'Nationwide (mobile)', 'Moroccan national emergency numbers', null)
on conflict (id) do update set label = excluded.label, number = excluded.number, scope = excluded.scope, source = excluded.source;
