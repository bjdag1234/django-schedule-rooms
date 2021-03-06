import datetime
import os

from django.test import TestCase
from django.core.urlresolvers import reverse

from schedule.models import Reservation, Rule, Occurrence, Room
from schedule.periods import Period, Month, Day
from schedule.utils import ReservationListManager

class TestReservation(TestCase):
    def setUp(self):
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        cal = Room(name="MyCal")
        cal.save()
        self.recurring_data = {
                'title': 'Recent Reservation',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
                'room': cal
               }
        self.data = {
                'title': 'Recent Reservation',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'room': cal
               }


    def test_recurring_reservation_get_occurrences(self):
        recurring_reservation = Reservation(**self.recurring_data)
        occurrences = recurring_reservation.get_occurrences(start=datetime.datetime(2008, 1, 12, 0, 0),
                                    end=datetime.datetime(2008, 1, 20, 0, 0))
        self.assertEquals(["%s to %s" %(o.start, o.end) for o in occurrences],
            ['2008-01-12 08:00:00 to 2008-01-12 09:00:00', '2008-01-19 08:00:00 to 2008-01-19 09:00:00'])

    def test_reservation_get_occurrences_after(self):
        recurring_reservation=Reservation(**self.recurring_data)
        recurring_reservation.save()
        occurrences = recurring_reservation.get_occurrences(start=datetime.datetime(2008, 1, 5),
            end = datetime.datetime(2008, 1, 6))
        occurrence = occurrences[0]
        occurrence2 = recurring_reservation.occurrences_after(datetime.datetime(2008,1,5)).next()
        self.assertEqual(occurrence, occurrence2)

    def test_get_occurrence(self):
        reservation = Reservation(**self.recurring_data)
        reservation.save()
        occurrence = reservation.get_occurrence(datetime.datetime(2008, 1, 5, 8, 0))
        self.assertEqual(occurrence.start, datetime.datetime(2008,1,5,8))
        occurrence.save()
        occurrence = reservation.get_occurrence(datetime.datetime(2008, 1, 5, 8, 0))
        self.assertTrue(occurrence.pk is not None)


class TestOccurrence(TestCase):
    def setUp(self):
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        cal = Room(name="MyCal")
        cal.save()
        self.recurring_data = {
                'title': 'Recent Reservation',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
                'room': cal
               }
        self.data = {
                'title': 'Recent Reservation',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'room': cal
               }
        self.recurring_reservation = Reservation(**self.recurring_data)
        self.recurring_reservation.save()
        self.start = datetime.datetime(2008, 1, 12, 0, 0)
        self.end = datetime.datetime(2008, 1, 27, 0, 0)

    def test_presisted_occurrences(self):
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        persisted_occurrence = occurrences[0]
        persisted_occurrence.save()
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertTrue(occurrences[0].pk)
        self.assertFalse(occurrences[1].pk)

    def test_moved_occurrences(self):
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        moved_occurrence = occurrences[1]
        span_pre = (moved_occurrence.start, moved_occurrence.end)
        span_post = [x + datetime.timedelta(hours=2) for x in span_pre]
        # check has_occurrence on both periods
        period_pre = Period([self.recurring_reservation], span_pre[0], span_pre[1])
        period_post = Period([self.recurring_reservation], span_post[0], span_post[1])
        self.assertTrue(period_pre.has_occurrences())
        self.assertFalse(period_post.has_occurrences())
        # move occurrence
        moved_occurrence.move(moved_occurrence.start+datetime.timedelta(hours=2),
                              moved_occurrence.end+datetime.timedelta(hours=2))
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertTrue(occurrences[1].moved)
        # check has_occurrence on both periods (the result should be reversed)
        period_pre = Period([self.recurring_reservation], span_pre[0], span_pre[1])
        period_post = Period([self.recurring_reservation], span_post[0], span_post[1])
        self.assertFalse(period_pre.has_occurrences())
        self.assertTrue(period_post.has_occurrences())
        # trigger bug discovered by gautamadude - modifying recurring reservation
        # breaks link between a persistent occurrence and the occurrence chain
        # leaving an "orphaned" occurrence
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertTrue(len(occurrences) == 3)
        self.recurring_reservation.start = datetime.datetime(2008, 1, 5, 8, 15)
        self.recurring_reservation.save()
        occurrences_later = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertEquals(len(occurrences_later), len(occurrences))

    def test_cancelled_occurrences(self):
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        cancelled_occurrence = occurrences[2]
        cancelled_occurrence.cancel()
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertTrue(occurrences[2].cancelled)
        cancelled_occurrence.uncancel()
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertFalse(occurrences[2].cancelled)
        # trigger bug discovered by gautamadude
        occurrences = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertTrue(len(occurrences) == 3)
        self.recurring_reservation.start = datetime.datetime(2008, 1, 5, 8, 15)
        self.recurring_reservation.save()
        occurrences_later = self.recurring_reservation.get_occurrences(start=self.start,
                                    end=self.end)
        self.assertEquals(len(occurrences_later), len(occurrences))

