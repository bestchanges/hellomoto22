import yaml
from mongoengine import ReferenceField, EmbeddedDocumentField

def decode_field(object, field_name, field_value):
    field = object._fields[field_name]
    if isinstance(field, ReferenceField):
        ref_object_type = field.document_type
        # object = ConfigurationGroup.objects(__raw__={'name': 'ETH+DCR'}).first()
        referenced_objects = ref_object_type.objects(__raw__=field_value)
        if len(referenced_objects) != 1:
            raise Exception(
                "reference filed '{}' has query '{}'. Returned {} entries instead of expected 1".format(
                    field_name, field_value, len(referenced_objects)))
        setattr(object, field_name, referenced_objects[0])
    elif isinstance(field, EmbeddedDocumentField):
        embedded_object = field.document_type()
        for field, value in field_value.items():
            decode_field(embedded_object, field, value)
        setattr(object, field_name, embedded_object)
    else:
        setattr(object, field_name, field_value)


def import_yaml_file(filename, doc_class, unique_check_field):
    file = open(filename, 'r')
    data = file.read()
    import_yaml(data, doc_class, unique_check_field)


def import_yaml(yaml_content, doc_class, unique_field = '_id'):
    object_num = 0
    for data in yaml.load_all(yaml_content):
        object_num += 1
        # try load existing object by provided unique field
        if not data or not data[unique_field]:
            raise Exception(
                "For {}, entry #{}, primary key '{}' not definied: {}".format(doc_class._class_name, object_num,
                                                                              unique_field, data))
        try:
            objects = doc_class.objects(__raw__={unique_field: data[unique_field]})
        except Exception as e:
            raise Exception("For {}, entry #{}, {}".format(doc_class._class_name, object_num, e))
        if len(objects) > 1:
            raise Exception(
                "For {}, entry #{}, for primary key '{}' = '{}' was found {} entries instead of expected 0-1".format(
                    doc_class._class_name, object_num, unique_field, data[unique_field], len(objects)))
        if not objects:
            # create new instance
            object = doc_class()
        else:
            object = objects[0]
        # now fill all fields to values
        for field_name, field_value in data.items():
            #try:
            decode_field(object, field_name, field_value)
            #except Exception as e:
            #    raise Exception("For {}, entry #{}: {}".format(doc_class._class_name, object_num, e))
        object.save()



