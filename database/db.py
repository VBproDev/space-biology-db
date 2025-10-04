"""
This file uses Peewee ORM to describe the schema of the tables used in the project
"""

from peewee import SqliteDatabase, Model, CharField, DateField, TextField, ForeignKeyField, CompositeKey

db = SqliteDatabase("space_bio.db", pragmas={
        'journal_mode': 'wal',
        'cache_size': -1 * 64000,
        'foreign_keys': 1,
        'ignore_check_constraints': 0,
        'synchronous': 0
    }
)

class BaseModel(Model):
    class Meta:
        database = db

class Pubs(BaseModel):
    link = CharField(primary_key=True)
    title = CharField(unique=True)
    date = DateField()
    content = TextField()
    
class Authors(BaseModel):
    name = CharField(primary_key=True)
    
class PubAuthors(Model):
    publication = ForeignKeyField(
        Pubs, 
        backref="authors", 
        on_delete="CASCADE", 
        on_update="CASCADE"
    )
    author = ForeignKeyField(
        Authors, 
        backref="publications", 
        on_delete="CASCADE", 
        on_update="CASCADE"
    )

    class Meta:
        database = db
        primary_key = CompositeKey('publication', 'author')