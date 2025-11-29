from django.contrib.gis.db import models

class Stop(models.Model):
    stop_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    location = models.PointField(geography=True)

    def __str__(self):
        return self.name


class Route(models.Model):
    route_id = models.CharField(max_length=50, unique=True)
    short_name = models.CharField(max_length=50)
    long_name = models.CharField(max_length=200)

    def __str__(self):
        return self.short_name


class Trip(models.Model):
    trip_id = models.CharField(max_length=50, unique=True)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    headsign = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.trip_id


class StopTime(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)
    stop_sequence = models.IntegerField()
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["trip", "stop_sequence"]
