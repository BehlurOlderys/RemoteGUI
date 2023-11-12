from threading import Event, Timer
import logging


logger = logging.getLogger(__name__)


def interval_polling(stop_event: Event, callback, interval_s: float, kill_event: Event):
    if kill_event is not None and kill_event.is_set():
        return
    callback()
    if not stop_event.is_set():
        Timer(interval_s, interval_polling, [stop_event, callback, interval_s, kill_event]).start()

    else:
        logger.debug("Interval polling stopped!")


def start_interval_polling(stop_event: Event, callback, interval_s: float, kill_event: Event):
    logger.debug(f"Starting new interval polling with {interval_s}s refresh")
    Timer(interval_s, interval_polling, [stop_event, callback, interval_s, kill_event]).start()
