-- Ejecuta esto una vez en Supabase → SQL Editor

create table if not exists equipos (
  cod_equipo   text primary key,
  nombre       text not null,
  escudo_url   text,
  actualizado  timestamptz default now()
);

create table if not exists jornadas (
  cod_grupo    text not null,
  jornada      int  not null,
  fecha        date,
  primary key (cod_grupo, jornada)
);

create table if not exists partidos (
  cod_grupo        text not null,
  jornada          int  not null,
  cod_local        text not null references equipos(cod_equipo),
  cod_visitante    text not null references equipos(cod_equipo),
  fecha            date,
  hora             text,
  campo            text,
  goles_local      int,
  goles_visitante  int,
  jugado           boolean default false,
  provisional      boolean default false,
  cod_acta         text,
  motivo_estado    text,
  actualizado      timestamptz default now(),
  primary key (cod_grupo, jornada, cod_local, cod_visitante)
);

create table if not exists clasificacion (
  cod_grupo    text not null,
  cod_equipo   text not null references equipos(cod_equipo),
  jornada      int,
  posicion     int,
  pj int, g int, e int, p int,
  gf int, gc int,
  puntos       int,
  racha        text,
  actualizado  timestamptz default now(),
  primary key (cod_grupo, cod_equipo)
);

-- Alineaciones (convocados) de los equipos seguidos, sacadas de las actas
create table if not exists alineaciones (
  cod_grupo    text not null,
  cod_equipo   text not null references equipos(cod_equipo),
  jornada      int  not null,
  cod_acta     text not null,
  cod_jugador  text not null,
  nombre       text not null,   -- abreviado: "Martin M."
  dorsal       int,
  posicion     text,
  titular      boolean,
  capitan      boolean,
  portero      boolean,
  esquema      text,
  entrenador   text,
  actualizado  timestamptz default now(),
  primary key (cod_acta, cod_equipo, cod_jugador)
);

-- Lectura pública (la web usa la clave anon); escritura solo con la service_role key
alter table equipos       enable row level security;
alter table jornadas      enable row level security;
alter table partidos      enable row level security;
alter table clasificacion enable row level security;
alter table alineaciones  enable row level security;

create policy "lectura publica" on equipos       for select using (true);
create policy "lectura publica" on jornadas      for select using (true);
create policy "lectura publica" on partidos      for select using (true);
create policy "lectura publica" on clasificacion for select using (true);
create policy "lectura publica" on alineaciones  for select using (true);
