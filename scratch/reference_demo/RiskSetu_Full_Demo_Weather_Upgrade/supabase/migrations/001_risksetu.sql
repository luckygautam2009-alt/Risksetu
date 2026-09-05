-- Apply once in a fresh Supabase project. All writes go through the authorized FastAPI API.
begin;
create extension if not exists postgis;

create table public.profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 full_name text not null default '', phone text, email text not null,
 role text not null default 'citizen' check(role in ('citizen','officer','admin')),
 officer_verified boolean not null default false, officer_requested boolean not null default false,
 preferred_language text not null default 'en' check(preferred_language in ('en','hi','as')),
 created_at timestamptz not null default now()
);
create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path='' as $$
begin
 insert into public.profiles(id,email,full_name) values(new.id,coalesce(new.email,''),coalesce(new.raw_user_meta_data->>'full_name',''));
 return new;
end; $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();

create or replace function public.is_officer() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.profiles where id=(select auth.uid()) and role in ('officer','admin') and officer_verified);
$$;
revoke all on function public.handle_new_user() from public;
revoke all on function public.is_officer() from public;
grant execute on function public.is_officer() to authenticated;

create table public.incidents (
 id uuid primary key default gen_random_uuid(), type text not null,
 latitude double precision not null check(latitude between -90 and 90), longitude double precision not null check(longitude between -180 and 180),
 description text not null check(length(description)<=3000), severity text not null check(severity in ('LOW','MODERATE','HIGH','CRITICAL')),
 status text not null default 'PENDING' check(status in ('PENDING','COMMUNITY_CONFIRMED','VERIFIED','REJECTED','RESOLVED')),
 source text not null, data_mode text not null check(data_mode in ('MOCK','LIVE','CACHED')),
 reporter_id uuid not null references public.profiles(id), confirmation_count int not null default 0,
 community_confidence_score double precision not null default 0 check(community_confidence_score between 0 and 1),
 client_id text not null unique, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 verified_at timestamptz, verified_by uuid references public.profiles(id), verification_notes text
);
create table public.incident_media (
 id uuid primary key default gen_random_uuid(), incident_id uuid not null references public.incidents(id) on delete cascade,
 storage_url text not null, media_type text not null, ai_analysis jsonb, created_at timestamptz not null default now()
);
create table public.incident_confirmations (
 id uuid primary key default gen_random_uuid(), incident_id uuid not null references public.incidents(id) on delete cascade,
 user_id uuid not null references public.profiles(id), confirmation text not null check(confirmation in ('YES','NO','UNSURE')),
 distance_from_incident double precision not null check(distance_from_incident between 0 and 1000),
 created_at timestamptz not null default now(), unique(incident_id,user_id)
);
create table public.risk_zones (
 id uuid primary key default gen_random_uuid(), name text, latitude double precision not null, longitude double precision not null,
 district text, state text, risk_score double precision not null check(risk_score between 0 and 100),
 risk_level text not null check(risk_level in ('LOW','MODERATE','HIGH','CRITICAL')), landslide_probability double precision check(landslide_probability between 0 and 1),
 rainfall_score double precision, terrain_score double precision, historical_score double precision, soil_score double precision, citizen_signal_score double precision,
 features jsonb not null default '{}', contributing_factors jsonb not null default '[]', radius_m double precision not null default 1000 check(radius_m>0),
 estimated_population bigint not null default 0 check(estimated_population>=0),
 source text not null, data_mode text not null check(data_mode in ('MOCK','LIVE','CACHED')), created_at timestamptz not null default now(), updated_at timestamptz not null
);
create table public.historical_landslides (
 id uuid primary key default gen_random_uuid(), external_id text not null unique,
 latitude double precision not null check(latitude between -90 and 90), longitude double precision not null check(longitude between -180 and 180),
 event_date date not null, district text, state text, source text not null, severity text, metadata jsonb not null default '{}',
 data_mode text not null check(data_mode in ('MOCK','LIVE','CACHED')), created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.weather_observations (
 id uuid primary key default gen_random_uuid(), latitude double precision not null, longitude double precision not null,
 rainfall_1h double precision, rainfall_24h double precision, rainfall_72h double precision,
 humidity double precision, temperature double precision, observation_time timestamptz not null,
 source text not null, data_mode text not null, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.shelters (
 id uuid primary key default gen_random_uuid(), name text not null, latitude double precision not null, longitude double precision not null,
 capacity int not null check(capacity>0), current_occupancy int not null default 0 check(current_occupancy>=0 and current_occupancy<=capacity),
 contact text not null, district text not null, state text not null, verified boolean not null default false, active boolean not null default true,
 verified_by uuid references public.profiles(id), source text not null, data_mode text not null,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.road_hazards (
 id uuid primary key default gen_random_uuid(), road_identifier text not null unique,
 latitude double precision not null, longitude double precision not null, geometry jsonb not null,
 risk_score double precision not null check(risk_score between 0 and 100), status text not null check(status in ('OPEN','CAUTION','BLOCKED')),
 incident_id uuid references public.incidents(id), updated_by uuid references public.profiles(id),
 source text not null, data_mode text not null, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.dispatches (
 id uuid primary key default gen_random_uuid(), incident_id uuid not null references public.incidents(id), assigned_team text not null,
 priority text not null, status text not null default 'ASSIGNED' check(status in ('ASSIGNED','COMPLETED')),
 instructions text not null, assigned_by uuid references public.profiles(id), created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.notifications (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references public.profiles(id), incident_id uuid references public.incidents(id),
 type text not null, title text not null, message text not null, severity text not null, read boolean not null default false,
 created_at timestamptz not null default now()
);
create table public.user_locations (
 id uuid primary key default gen_random_uuid(), user_id uuid not null unique references public.profiles(id) on delete cascade,
 latitude double precision not null, longitude double precision not null,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.audit_logs (
 id uuid primary key default gen_random_uuid(), actor_id uuid not null references public.profiles(id), action text not null,
 target_id text not null, detail jsonb not null default '{}', created_at timestamptz not null default now()
);

-- Deny browser writes, including role updates. The API verifies Supabase identity
-- and database approval on every privileged request before using the service role.
do $$ declare t text; begin
 foreach t in array array['profiles','incidents','incident_media','incident_confirmations','risk_zones','historical_landslides','weather_observations','shelters','road_hazards','dispatches','notifications','user_locations','audit_logs'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon, authenticated',t);
  execute format('grant select on public.%I to authenticated',t);
  execute format('grant all on public.%I to service_role',t);
 end loop;
end $$;
create policy profile_read on public.profiles for select to authenticated using(id=(select auth.uid()) or public.is_officer());
create policy incident_read on public.incidents for select to authenticated using(reporter_id=(select auth.uid()) or public.is_officer());
create policy confirmation_read on public.incident_confirmations for select to authenticated using(user_id=(select auth.uid()) or public.is_officer());
create policy media_read on public.incident_media for select to authenticated using(public.is_officer() or exists(select 1 from public.incidents i where i.id=incident_id and i.reporter_id=(select auth.uid())));
create policy risk_read on public.risk_zones for select to authenticated using(true);
create policy history_read on public.historical_landslides for select to authenticated using(true);
create policy weather_read on public.weather_observations for select to authenticated using(true);
create policy shelter_read on public.shelters for select to authenticated using(verified or public.is_officer());
create policy road_read on public.road_hazards for select to authenticated using(true);
create policy dispatch_read on public.dispatches for select to authenticated using(public.is_officer());
create policy notification_read on public.notifications for select to authenticated using(user_id=(select auth.uid()));
create policy location_read on public.user_locations for select to authenticated using(user_id=(select auth.uid()));
create policy audit_read on public.audit_logs for select to authenticated using(public.is_officer());

create index incidents_status_time on public.incidents(status,created_at desc);
create index incidents_location on public.incidents using gist((st_setsrid(st_makepoint(longitude,latitude),4326)::geography));
create index zones_location on public.risk_zones using gist((st_setsrid(st_makepoint(longitude,latitude),4326)::geography));
create index history_location on public.historical_landslides using gist((st_setsrid(st_makepoint(longitude,latitude),4326)::geography));
create index shelters_location on public.shelters(latitude,longitude);
create index roads_location on public.road_hazards(latitude,longitude);
create index zones_level on public.risk_zones(risk_level,updated_at);
create index history_time on public.historical_landslides(event_date,state,district);
create index weather_time on public.weather_observations(observation_time);
create index notifications_user on public.notifications(user_id,created_at desc);
create index user_locations_time on public.user_locations(updated_at);

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
 values('incident-media','incident-media',false,5242880,array['image/jpeg','image/png','image/webp','video/mp4']) on conflict(id) do nothing;
-- Private media is served through authorized API requests with short-lived URLs.
-- No direct storage write/read policy is granted to browser clients.

do $$ declare t text; begin
 foreach t in array array['incidents','incident_confirmations','notifications','road_hazards','risk_zones','shelters'] loop
  if exists(select 1 from pg_publication where pubname='supabase_realtime') and not exists(select 1 from pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename=t) then
   execute format('alter publication supabase_realtime add table public.%I',t);
  end if;
 end loop;
end $$;
commit;
