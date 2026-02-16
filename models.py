from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone

Base = declarative_base()


class Queue(Base):
    __tablename__ = 'queue'

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_active = Column(Boolean, default=True, nullable=False)
    discipline_name = Column(String, nullable=False)
    work_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    paused = Column(Boolean, default=False, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    items = relationship('QueueItem', back_populates='queue', order_by='QueueItem.position')


class QueueItem(Base):
    __tablename__ = 'queue_item'

    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_id = Column(Integer, ForeignKey('queue.id'), nullable=False)
    student_isu_id = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    status = Column(String, default='waiting', nullable=False)
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    service_start_at = Column(DateTime, nullable=True)
    service_end_at = Column(DateTime, nullable=True)

    queue = relationship('Queue', back_populates='items')


engine = create_engine('sqlite:///queue.db', echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)
