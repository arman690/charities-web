from rest_framework import status, generics
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCharityOwner, IsBenefactor
from charities.models import Task
from charities.serializers import (
    TaskSerializer, CharitySerializer, BenefactorSerializer
)


class BenefactorRegistration(APIView):
    def post(self, request, format=None):
        serializer = BenefactorSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    
class CharityRegistration(APIView):
    def post(self, request, format=None):
        serializer = CharitySerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    
class Tasks(generics.ListCreateAPIView):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.all_related_tasks_to_user(self.request.user)

    def post(self, request, *args, **kwargs):
        data = {
            **request.data,
            "charity_id": request.user.charity.id
        }
        serializer = self.serializer_class(data = data)
        serializer.is_valid(raise_exception = True)
        serializer.save()
        return Response(serializer.data, status = status.HTTP_201_CREATED)

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            self.permission_classes = [IsAuthenticated, ]
        else:
            self.permission_classes = [IsCharityOwner, ]

        return [permission() for permission in self.permission_classes]

    def filter_queryset(self, queryset):
        filter_lookups = {}
        for name, value in Task.filtering_lookups:
            param = self.request.GET.get(value)
            if param:
                filter_lookups[name] = param
        exclude_lookups = {}
        for name, value in Task.excluding_lookups:
            param = self.request.GET.get(value)
            if param:
                exclude_lookups[name] = param

        return queryset.filter(**filter_lookups).exclude(**exclude_lookups)


class TaskRequest(APIView):
    def get(self, request, task_id, format=None):
        try:
            task = Task.objects.get(pk=task_id)

            if not request.user.is_benefactor:
                return Response({'detail': 'Only benefactors can request tasks.'}, status=status.HTTP_403_FORBIDDEN)

            if task.state != Task.TaskStatus.PENDING:
                return Response({'detail': 'This task is not pending.'}, status=status.HTTP_404_NOT_FOUND)

            # Assign the task to the benefactor
            task.assign_to_benefactor(request.user.benefactor)
            task.save()
            return Response({'detail': 'Request sent.'}, status=status.HTTP_200_OK)

        except Task.DoesNotExist:
            return Response({'detail': 'Task not found.'}, status=status.HTTP_404_NOT_FOUND)

        
class TaskResponse(APIView):
    def post(self, request, task_id, format=None):
        if request.user.is_charity:
            task = Task.objects.get(pk=task_id)
            response = request.data['response']
            if not (response == 'R' or response == 'A') :
                return Response({'detail': 'Required field ("A" for accepted / "R" for rejected)'}, status=status.HTTP_400_BAD_REQUEST)
            elif task.state != Task.TaskStatus.WAITING:
                return Response({'detail': 'This task is not waiting.'}, status=status.HTTP_404_NOT_FOUND)
            
            else:

                if response == 'A':
                    task.state = Task.TaskStatus.ASSIGNED
                    task.save()
                    return Response({'detail': 'Response sent.'}, status=status.HTTP_200_OK)
                elif response == 'R':
                    task.state = Task.TaskStatus.PENDING
                    task.assigned_benefactor = None
                    task.save()
                    return Response({'detail': 'Response sent.'}, status=status.HTTP_200_OK)
        
        
        else:
            return Response({'detail': 'Only charities can respond to task requests.'}, status=status.HTTP_403_FORBIDDEN)


class DoneTask(APIView):
    permission_classes = [IsAuthenticated, IsCharityOwner]

    def post(self, request, task_id, format=None):
        try:
            task = Task.objects.get(pk=task_id)

            if task.state != Task.TaskStatus.ASSIGNED:
                return Response({'detail': 'Task is not assigned yet.'}, status=status.HTTP_404_NOT_FOUND)

            # Set the task state to DONE
            task.done()
            
            return Response({'detail': 'Task has been done successfully.'}, status=status.HTTP_200_OK)

        except Task.DoesNotExist:
            return Response({'detail': 'Task not found.'}, status=status.HTTP_404_NOT_FOUND)