from django.shortcuts import render

# Create your views here.

def index(request):
    return render(request, '/Users/choiyoungmi/Desktop/code/capstone/com/project/mysite/pybo/templates/pybo/main.html')
