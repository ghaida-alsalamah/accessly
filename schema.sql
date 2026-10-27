CREATE TABLE IF NOT EXISTS users(
user_id  INTEGER PRIMARY KEY NOT NULL GENERATED ALWAYS AS IDENTITY ,
user_name VARCHAR(100) NOT NULL,
user_email  VARCHAR(100) NOT NULL UNIQUE,
preferred_language TEXT NOT NULL,
privacy_consent BOOLEAN NOT NULL ,
consent_date TIMESTAMP NOT NULL,
otp_code TEXT ,
otp_created_at TIMESTAMP ,
otp_attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS needs(
need_id INTEGER PRIMARY KEY NOT NULL GENERATED ALWAYS AS IDENTITY ,
user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE ,
need_name VARCHAR(1000) NOT NULL,
is_custom BOOLEAN NOT NULL,
is_active BOOLEAN NOT NULL DEFAULT TRUE ,
UNIQUE (user_id,need_name)
);
CREATE TABLE IF NOT EXISTS requests(
request_id INTEGER PRIMARY KEY NOT NULL GENERATED ALWAYS AS IDENTITY,
user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
event_url TEXT NOT NULL ,
event_name text not null ,
event_date DATE ,
event_location TEXT ,
organizer_name TEXT ,
organizer_email TEXT ,
email_subject TEXT not null ,
sent_at TIMESTAMP not null,
overall_status TEXT not null DEFAULT 'PENDING'
CHECK (overall_status IN ('PENDING','CONFIRMED','PARTIALLY CONFIRMED','MORE INFORMATION NEEDED','UNAVAILABLE','UNCLEAR'))
);
CREATE TABLE IF NOT EXISTS request_needs(
request_id INTEGER NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE ,
need_id INTEGER NOT NULL REFERENCES needs(need_id) ON DELETE CASCADE,
status TEXT NOT NULL DEFAULT 'PENDING'
CHECK (status IN ('PENDING','CONFIRMED','NOT CONFIRMED','NOT APPLICABLE','UNAVAILABLE','UNCLEAR','UNKNOWN','MORE INFORMATION NEEDED')),
last_notified_status TEXT ,
PRIMARY KEY (request_id,need_id)
);
