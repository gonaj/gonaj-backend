from rest_framework import serializers
from .models import Stop, Route, Trip, StopTime
from django.contrib.gis.geos import Point

class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = "__all__"

class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = "__all__"

class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = "__all__"

class StopTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StopTime
        fields = "__all__"
