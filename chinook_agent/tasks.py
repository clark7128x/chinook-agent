from __future__ import annotations

import random

from .database import ReadOnlyDatabase

TASK_COUNT = 50
LEVEL_SIZES = {"single": 17, "join": 17, "aggregate": 16}


class TaskError(RuntimeError):
    pass


def quote(value) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)


def rows(database: ReadOnlyDatabase, sql: str) -> list[list]:
    result = database.execute(sql)
    if not result["ok"]:
        raise TaskError(f"{sql}: {result['error']}")
    return result["rows"]


def one(database: ReadOnlyDatabase, sql: str):
    found = rows(database, sql)
    if not found:
        raise TaskError(f"порожній результат: {sql}")
    return found[0][0]


def single_tasks(db: ReadOnlyDatabase, rng: random.Random) -> list[tuple[str, str]]:
    country = one(db, "SELECT Country FROM Customer GROUP BY Country ORDER BY COUNT(*) DESC, Country LIMIT 1")
    customer_id = one(db, f"SELECT CustomerId FROM Customer WHERE Country = {quote(country)} ORDER BY CustomerId LIMIT 1")
    album_id = one(db, "SELECT AlbumId FROM Album ORDER BY AlbumId LIMIT 1")
    genre_id, genre = rows(db, "SELECT GenreId, Name FROM Genre ORDER BY GenreId LIMIT 1")[0]
    track_id = one(db, "SELECT TrackId FROM Track ORDER BY TrackId LIMIT 1")
    media_id = one(db, "SELECT MediaTypeId FROM MediaType ORDER BY MediaTypeId LIMIT 1")

    return [
        ("Скільки всього артистів у базі?", "SELECT COUNT(*) FROM Artist"),
        ("Скільки всього треків у базі?", "SELECT COUNT(*) FROM Track"),
        (f"Скільки клієнтів з країни {country}?",
         f"SELECT COUNT(*) FROM Customer WHERE Country = {quote(country)}"),
        (f"Яка назва альбому з AlbumId = {album_id}?",
         f"SELECT Title FROM Album WHERE AlbumId = {album_id}"),
        ("Скільки жанрів у базі?", "SELECT COUNT(*) FROM Genre"),
        (f"Яка ціна треку з TrackId = {track_id}?",
         f"SELECT UnitPrice FROM Track WHERE TrackId = {track_id}"),
        (f"Скільки треків має жанр «{genre}» з GenreId = {genre_id}?",
         f"SELECT COUNT(*) FROM Track WHERE GenreId = {genre_id}"),
        ("Яка тривалість найдовшого треку в мілісекундах?", "SELECT MAX(Milliseconds) FROM Track"),
        ("Скільки плейлистів у базі?", "SELECT COUNT(*) FROM Playlist"),
        (f"У якому місті живе клієнт з CustomerId = {customer_id}?",
         f"SELECT City FROM Customer WHERE CustomerId = {customer_id}"),
        ("Скільки рахунків у базі?", "SELECT COUNT(*) FROM Invoice"),
        ("Яка найбільша сума рахунку в полі Total?", "SELECT MAX(Total) FROM Invoice"),
        ("Скільки співробітників у базі?", "SELECT COUNT(*) FROM Employee"),
        (f"Який email клієнта з CustomerId = {customer_id}?",
         f"SELECT Email FROM Customer WHERE CustomerId = {customer_id}"),
        ("Скільки треків мають ціну вище 0.99?", "SELECT COUNT(*) FROM Track WHERE UnitPrice > 0.99"),
        (f"Як називається медіатип з MediaTypeId = {media_id}?",
         f"SELECT Name FROM MediaType WHERE MediaTypeId = {media_id}"),
        ("Скільки різних країн серед клієнтів?", "SELECT COUNT(DISTINCT Country) FROM Customer"),
    ]


def join_tasks(db: ReadOnlyDatabase, rng: random.Random) -> list[tuple[str, str]]:
    artist = one(db, "SELECT ar.Name FROM Artist ar JOIN Album al ON al.ArtistId = ar.ArtistId "
                     "GROUP BY ar.ArtistId ORDER BY COUNT(*) DESC, ar.Name LIMIT 1")
    album_id, album_title = rows(db, "SELECT AlbumId, Title FROM Album ORDER BY AlbumId LIMIT 1")[0]
    track_id, track_name = rows(db, "SELECT TrackId, Name FROM Track ORDER BY TrackId LIMIT 1")[0]
    playlist_id, playlist = rows(db, "SELECT PlaylistId, Name FROM Playlist ORDER BY PlaylistId LIMIT 1")[0]
    playlist2_id = one(db, "SELECT PlaylistId FROM Playlist ORDER BY PlaylistId DESC LIMIT 1")
    invoice_id = one(db, "SELECT InvoiceId FROM Invoice ORDER BY InvoiceId LIMIT 1")
    customer_id, first, last = rows(db, "SELECT CustomerId, FirstName, LastName FROM Customer ORDER BY CustomerId LIMIT 1")[0]
    employee_id, emp_first, emp_last = rows(db, "SELECT EmployeeId, FirstName, LastName FROM Employee ORDER BY EmployeeId LIMIT 1")[0]
    subordinate_id, sub_first, sub_last = rows(
        db, "SELECT EmployeeId, FirstName, LastName FROM Employee WHERE ReportsTo IS NOT NULL ORDER BY EmployeeId LIMIT 1"
    )[0]
    pl_track_id = one(db, "SELECT TrackId FROM PlaylistTrack ORDER BY TrackId LIMIT 1")

    return [
        (f"Скільки альбомів у артиста «{artist}»?",
         "SELECT COUNT(*) FROM Album al JOIN Artist ar ON al.ArtistId = ar.ArtistId "
         f"WHERE ar.Name = {quote(artist)}"),
        (f"Назви перші п'ять альбомів артиста «{artist}» за алфавітом.",
         "SELECT al.Title FROM Album al JOIN Artist ar ON al.ArtistId = ar.ArtistId "
         f"WHERE ar.Name = {quote(artist)} ORDER BY al.Title LIMIT 5"),
        (f"Скільки треків в альбомі «{album_title}» (AlbumId = {album_id})?",
         "SELECT COUNT(*) FROM Track t JOIN Album al ON t.AlbumId = al.AlbumId "
         f"WHERE al.AlbumId = {album_id}"),
        (f"Який жанр треку «{track_name}» з TrackId = {track_id}?",
         "SELECT g.Name FROM Track t JOIN Genre g ON t.GenreId = g.GenreId "
         f"WHERE t.TrackId = {track_id}"),
        (f"Скільки треків у плейлисті «{playlist}» (PlaylistId = {playlist_id})?",
         "SELECT COUNT(*) FROM PlaylistTrack pt JOIN Playlist p ON pt.PlaylistId = p.PlaylistId "
         f"WHERE p.PlaylistId = {playlist_id}"),
        (f"Як звати клієнта за рахунком InvoiceId = {invoice_id}? Назви ім'я та прізвище.",
         "SELECT c.FirstName, c.LastName FROM Invoice i JOIN Customer c ON i.CustomerId = c.CustomerId "
         f"WHERE i.InvoiceId = {invoice_id}"),
        (f"Скільки рахунків має клієнт {first} {last}?",
         "SELECT COUNT(*) FROM Invoice i JOIN Customer c ON i.CustomerId = c.CustomerId "
         f"WHERE c.FirstName = {quote(first)} AND c.LastName = {quote(last)}"),
        (f"Назви перші п'ять треків у рахунку InvoiceId = {invoice_id} за зростанням TrackId.",
         "SELECT t.Name FROM InvoiceLine il JOIN Track t ON il.TrackId = t.TrackId "
         f"WHERE il.InvoiceId = {invoice_id} ORDER BY t.TrackId LIMIT 5"),
        (f"Скільки клієнтів обслуговує співробітник {emp_first} {emp_last} (EmployeeId = {employee_id})?",
         "SELECT COUNT(*) FROM Customer c JOIN Employee e ON c.SupportRepId = e.EmployeeId "
         f"WHERE e.EmployeeId = {employee_id}"),
        (f"З якої країни клієнт за рахунком InvoiceId = {invoice_id}?",
         "SELECT c.Country FROM Invoice i JOIN Customer c ON i.CustomerId = c.CustomerId "
         f"WHERE i.InvoiceId = {invoice_id}"),
        (f"Який медіатип треку з TrackId = {track_id}?",
         "SELECT m.Name FROM Track t JOIN MediaType m ON t.MediaTypeId = m.MediaTypeId "
         f"WHERE t.TrackId = {track_id}"),
        (f"Який артист виконує трек з TrackId = {track_id}?",
         "SELECT ar.Name FROM Track t JOIN Album al ON t.AlbumId = al.AlbumId "
         f"JOIN Artist ar ON al.ArtistId = ar.ArtistId WHERE t.TrackId = {track_id}"),
        (f"Скільки треків у плейлисті з PlaylistId = {playlist2_id}?",
         "SELECT COUNT(*) FROM PlaylistTrack pt JOIN Playlist p ON pt.PlaylistId = p.PlaylistId "
         f"WHERE p.PlaylistId = {playlist2_id}"),
        (f"Хто керівник співробітника {sub_first} {sub_last} (EmployeeId = {subordinate_id})? Назви ім'я та прізвище.",
         "SELECT m.FirstName, m.LastName FROM Employee e JOIN Employee m ON e.ReportsTo = m.EmployeeId "
         f"WHERE e.EmployeeId = {subordinate_id}"),
        (f"У яких плейлистах є трек з TrackId = {pl_track_id}? Назви перші п'ять за алфавітом.",
         "SELECT p.Name FROM PlaylistTrack pt JOIN Playlist p ON pt.PlaylistId = p.PlaylistId "
         f"WHERE pt.TrackId = {pl_track_id} ORDER BY p.Name LIMIT 5"),
        (f"Скільки рядків у рахунку InvoiceId = {invoice_id}?",
         "SELECT COUNT(*) FROM InvoiceLine il JOIN Invoice i ON il.InvoiceId = i.InvoiceId "
         f"WHERE i.InvoiceId = {invoice_id}"),
        (f"З якого альбому трек з TrackId = {track_id}?",
         "SELECT al.Title FROM Track t JOIN Album al ON t.AlbumId = al.AlbumId "
         f"WHERE t.TrackId = {track_id}"),
    ]


def aggregate_tasks(db: ReadOnlyDatabase, rng: random.Random) -> list[tuple[str, str]]:
    country = one(db, "SELECT BillingCountry FROM Invoice GROUP BY BillingCountry ORDER BY COUNT(*) DESC, BillingCountry LIMIT 1")
    genre_id, genre = rows(db, "SELECT GenreId, Name FROM Genre ORDER BY GenreId LIMIT 1")[0]
    sold_track_id = one(db, "SELECT TrackId FROM InvoiceLine GROUP BY TrackId ORDER BY SUM(Quantity) DESC, TrackId LIMIT 1")

    return [
        ("Скільки артистів мають більше трьох альбомів?",
         "SELECT COUNT(*) FROM (SELECT ArtistId FROM Album GROUP BY ArtistId HAVING COUNT(*) > 3)"),
        ("Який артист має найбільше альбомів? При рівності обери першого за алфавітом.",
         "SELECT ar.Name FROM Artist ar JOIN Album al ON al.ArtistId = ar.ArtistId "
         "GROUP BY ar.ArtistId ORDER BY COUNT(*) DESC, ar.Name LIMIT 1"),
        (f"Яка загальна сума рахунків по країні {country}? Округли до центів.",
         f"SELECT ROUND(SUM(Total), 2) FROM Invoice WHERE BillingCountry = {quote(country)}"),
        ("Яка країна принесла найбільшу виручку за рахунками?",
         "SELECT BillingCountry FROM Invoice GROUP BY BillingCountry ORDER BY SUM(Total) DESC, BillingCountry LIMIT 1"),
        ("Скільки жанрів мають більше 100 треків?",
         "SELECT COUNT(*) FROM (SELECT GenreId FROM Track GROUP BY GenreId HAVING COUNT(*) > 100)"),
        (f"Яка середня ціна треку жанру «{genre}» з GenreId = {genre_id}? Округли до центів.",
         f"SELECT ROUND(AVG(UnitPrice), 2) FROM Track WHERE GenreId = {genre_id}"),
        (f"Яка виручка по жанру «{genre}» з GenreId = {genre_id}? Округли до центів.",
         "SELECT ROUND(SUM(il.UnitPrice * il.Quantity), 2) FROM InvoiceLine il "
         f"JOIN Track t ON il.TrackId = t.TrackId WHERE t.GenreId = {genre_id}"),
        ("Назви п'ять треків, які продавалися найбільше одиниць. При рівності впорядкуй за назвою.",
         "SELECT t.Name FROM InvoiceLine il JOIN Track t ON il.TrackId = t.TrackId "
         "GROUP BY t.TrackId ORDER BY SUM(il.Quantity) DESC, t.Name LIMIT 5"),
        ("Скільки клієнтів витратили загалом більше 40?",
         "SELECT COUNT(*) FROM (SELECT CustomerId FROM Invoice GROUP BY CustomerId HAVING SUM(Total) > 40)"),
        ("Який клієнт витратив найбільше? Назви ім'я та прізвище. При рівності обери першого за прізвищем.",
         "SELECT c.FirstName, c.LastName FROM Invoice i JOIN Customer c ON i.CustomerId = c.CustomerId "
         "GROUP BY c.CustomerId ORDER BY SUM(i.Total) DESC, c.LastName LIMIT 1"),
        (f"Скільки одиниць треку з TrackId = {sold_track_id} продано?",
         f"SELECT SUM(Quantity) FROM InvoiceLine WHERE TrackId = {sold_track_id}"),
        ("Скільки країн мають більше п'яти клієнтів?",
         "SELECT COUNT(*) FROM (SELECT Country FROM Customer GROUP BY Country HAVING COUNT(*) > 5)"),
        (f"Яка середня сума рахунку по країні {country}? Округли до центів.",
         f"SELECT ROUND(AVG(Total), 2) FROM Invoice WHERE BillingCountry = {quote(country)}"),
        ("Який жанр приніс найбільшу виручку? При рівності обери перший за алфавітом.",
         "SELECT g.Name FROM InvoiceLine il JOIN Track t ON il.TrackId = t.TrackId "
         "JOIN Genre g ON t.GenreId = g.GenreId GROUP BY g.GenreId ORDER BY SUM(il.UnitPrice * il.Quantity) DESC, g.Name LIMIT 1"),
        (f"Скільки треків жанру «{genre}» з GenreId = {genre_id} довші за 5 хвилин?",
         f"SELECT COUNT(*) FROM Track WHERE GenreId = {genre_id} AND Milliseconds > 300000"),
        (f"Яка найбільша сума рахунку по країні {country}?",
         f"SELECT MAX(Total) FROM Invoice WHERE BillingCountry = {quote(country)}"),
    ]


def build_tasks(db: ReadOnlyDatabase, seed: int) -> list[dict]:
    rng = random.Random(seed)
    builders = {"single": single_tasks, "join": join_tasks, "aggregate": aggregate_tasks}
    tasks: list[dict] = []
    for level, builder in builders.items():
        pairs = builder(db, rng)
        if len(pairs) != LEVEL_SIZES[level]:
            raise TaskError(f"{level}: очікувано {LEVEL_SIZES[level]} задач, отримано {len(pairs)}")
        for index, (question, sql) in enumerate(pairs, start=1):
            result = db.execute(sql)
            if not result["ok"]:
                raise TaskError(f"{level}/{index}: {result['error']}")
            if not result["rows"]:
                raise TaskError(f"{level}/{index}: еталонний запит не повертає рядків")
            if result["truncated"]:
                raise TaskError(f"{level}/{index}: еталонний запит обрізаний лімітом рядків")
            if any(cell is None for row in result["rows"] for cell in row):
                raise TaskError(f"{level}/{index}: еталон містить NULL")
            tasks.append(
                {
                    "id": f"{level}-{index:02d}",
                    "level": level,
                    "question": question,
                    "gold_sql": sql,
                    "gold_columns": result["columns"],
                    "gold_rows": result["rows"],
                }
            )
    if len(tasks) != TASK_COUNT:
        raise TaskError(f"каталог має дати {TASK_COUNT} задач, отримано {len(tasks)}")
    return tasks
