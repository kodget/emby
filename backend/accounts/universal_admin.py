from django.apps import apps
from django.contrib import admin
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.exceptions import FieldDoesNotExist
import json
from django.core.serializers import serialize
from django.db import models
from rest_framework import status

def get_model_schema(model):
    """Generate a simple schema dict for a Django model's fields."""
    fields = []
    for f in model._meta.get_fields():
        if f.is_relation and f.many_to_many and not f.related_model:
            continue
            
        field_info = {
            "name": f.name,
            "verbose_name": getattr(f, 'verbose_name', f.name).title(),
            "type": f.get_internal_type() if hasattr(f, 'get_internal_type') else 'Relation',
            "is_relation": f.is_relation,
            "auto_created": f.auto_created,
            "editable": getattr(f, 'editable', False),
            "primary_key": getattr(f, 'primary_key', False),
        }

        if f.is_relation:
            field_info["related_model"] = f.related_model._meta.label if f.related_model else None
            field_info["many_to_many"] = f.many_to_many
            field_info["many_to_one"] = f.many_to_one
            field_info["one_to_many"] = f.one_to_many
            field_info["one_to_one"] = f.one_to_one
            
        if getattr(f, 'choices', None):
            field_info["choices"] = [{"value": c[0], "label": str(c[1])} for c in f.choices]
            
        fields.append(field_info)
        
    return {
        "app_label": model._meta.app_label,
        "model_name": model._meta.model_name,
        "verbose_name": model._meta.verbose_name.title(),
        "verbose_name_plural": model._meta.verbose_name_plural.title(),
        "fields": fields
    }

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_schema(request):
    """Returns all models registered in the Django admin site and their schemas."""
    # Get all models registered in the default admin site
    registered_models = admin.site._registry.keys()
    
    schema_map = {}
    
    for model in registered_models:
        app_label = model._meta.app_label
        if app_label not in schema_map:
            schema_map[app_label] = {
                "app_label": app_label,
                "app_name": apps.get_app_config(app_label).verbose_name,
                "models": []
            }
            
        schema_map[app_label]["models"].append(get_model_schema(model))
        
    # Convert dict to list
    return Response(list(schema_map.values()))

def get_model_from_kwargs(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_data_list(request, app_label, model_name):
    model = get_model_from_kwargs(app_label, model_name)
    if not model:
        return Response({"error": "Model not found"}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        # Pagination (simplified for now)
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        offset = (page - 1) * limit
        
        queryset = model.objects.all()
        total = queryset.count()
        
        # Simple JSON serialization (not deep, handles simple fields and converts FK to IDs)
        # We use Django's built-in python serializer to get dicts
        from django.core.serializers.python import Serializer
        serializer = Serializer()
        
        # It's better to manually build the dict to include IDs of relations 
        # because Django's serializer puts PK in 'pk' and fields in 'fields'.
        results = []
        for obj in queryset[offset:offset+limit]:
            item = {"id": obj.pk}
            for f in model._meta.get_fields():
                if f.auto_created and not f.primary_key:
                    continue
                if hasattr(obj, f.name):
                    val = getattr(obj, f.name)
                    if f.is_relation and f.many_to_many:
                        # Skip full evaluation of M2M for list views to save queries
                        item[f.name] = [v.pk for v in val.all()] if val else []
                    elif f.is_relation and f.many_to_one:
                        # FK
                        item[f.name] = val.pk if val else None
                        item[f"{f.name}_display"] = str(val) if val else None
                    else:
                        if isinstance(val, models.Model):
                             item[f.name] = val.pk
                        else:
                             item[f.name] = str(val) if val is not None else None
            results.append(item)
            
        return Response({
            "results": results,
            "total": total,
            "page": page,
            "limit": limit
        })

    elif request.method == 'POST':
        # Create
        data = request.data
        try:
            # Very naive create - expects data to match field names exactly
            # Will need special handling for M2M
            m2m_data = {}
            create_data = {}
            for f in model._meta.get_fields():
                if f.name in data:
                    if f.many_to_many:
                        m2m_data[f.name] = data[f.name]
                    elif f.is_relation and f.many_to_one:
                        # Convert ID to instance
                        rel_model = f.related_model
                        if data[f.name]:
                            create_data[f.name] = rel_model.objects.get(pk=data[f.name])
                        else:
                            create_data[f.name] = None
                    else:
                        create_data[f.name] = data[f.name]
            
            obj = model.objects.create(**create_data)
            
            for m2m_field, m2m_values in m2m_data.items():
                if m2m_values:
                    getattr(obj, m2m_field).set(m2m_values)
                    
            return Response({"id": obj.pk, "status": "created"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_data_detail(request, app_label, model_name, pk):
    model = get_model_from_kwargs(app_label, model_name)
    if not model:
        return Response({"error": "Model not found"}, status=status.HTTP_404_NOT_FOUND)
        
    try:
        obj = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        item = {"id": obj.pk}
        for f in model._meta.get_fields():
            if f.auto_created and not f.primary_key:
                continue
            if hasattr(obj, f.name):
                val = getattr(obj, f.name)
                if f.is_relation and f.many_to_many:
                    item[f.name] = [v.pk for v in val.all()] if val else []
                elif f.is_relation and f.many_to_one:
                    item[f.name] = val.pk if val else None
                    item[f"{f.name}_display"] = str(val) if val else None
                else:
                    if isinstance(val, models.Model):
                         item[f.name] = val.pk
                    else:
                         item[f.name] = val # Keep original type if possible, JS will handle
        return Response(item)
        
    elif request.method == 'PUT':
        data = request.data
        try:
            m2m_data = {}
            for f in model._meta.get_fields():
                if f.name in data:
                    if f.many_to_many:
                        m2m_data[f.name] = data[f.name]
                    elif f.is_relation and f.many_to_one:
                        rel_model = f.related_model
                        if data[f.name]:
                            setattr(obj, f.name, rel_model.objects.get(pk=data[f.name]))
                        else:
                            setattr(obj, f.name, None)
                    else:
                        setattr(obj, f.name, data[f.name])
            obj.save()
            
            for m2m_field, m2m_values in m2m_data.items():
                if m2m_values is not None:
                    getattr(obj, m2m_field).set(m2m_values)
                    
            return Response({"status": "updated"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
    elif request.method == 'DELETE':
        obj.delete()
        return Response({"status": "deleted"}, status=status.HTTP_204_NO_CONTENT)
