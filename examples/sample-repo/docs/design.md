# Design notes

Links are stored in SQLite with an auto-increment id. The short code is the
id written in base 62, so codes stay short and are never reused. There is no
expiry and no click tracking yet.
