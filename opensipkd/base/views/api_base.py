from datetime import datetime, date
import logging
import colander
from decimal import Decimal
from math import e, exp, log
from pyramid.response import Response
from pyramid.response import Response
from pyramid.httpexceptions import *
import colander
from deform import Form, ValidationFailure
from deform.widget import SelectWidget
from opensipkd.base.models import DBSession
from opensipkd.tools.buttons import btn_save, btn_cancel
from opensipkd.tools import get_settings
from opensipkd.models import User
from opensipkd.base.views.common import DataTables, ColumnDT
from . import api_messages
from ..tools import obj2json


from pyramid_restful.views import APIView
import json
_log = logging.getLogger(__name__)


class ApiViews(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.req = kwargs.get("request", None)
        self.user = User
        self.db_session = DBSession
        self.buttons = (btn_save, btn_cancel)
        self.table = None
        self.pkey = ("id",)
        self.orders = None
        self.bindings = {}
        self.id = -1
        self.autocomplete = True
        self.form_widget = None
        self.columns = None
        self.list_schema = None
        self.add_schema = None
        self.edit_schema = None
        self.psize = 25
        self.settings = get_settings()
        self.page = 1
        self.http_bad_request = HTTPBadRequest
        self.http_not_found = HTTPNotFound
        self.http_forbidden = HTTPForbidden
        self.http_not_acceptable = HTTPNotAcceptable
        self.response = Response
        self.list_permission = None
        self.add_permission = None
        self.edit_permission = None
        self.delete_permission = None
        
    def get_params(self, key, default=None):
        return self.settings.get(key, default)
    
    def list_join(self, query, **kw):
        return query

    def list_filter(self, query, **kw):
        id_ = kw.get("id", 0)
        kode = kw.get("kode", 0)
        if id_:
            query = query.filter(self.table.id == int(id_))
        elif kode:
            query = query.filter(self.table.kode == kode)
        return query

    def get_list(self, **kwargs):
        """
        parameter
        list_schema optional
        list_join callback
        list_filter callback
        """
        url = []
        select_list = {}
        list_schema = kwargs.get("list_schema")
        if not list_schema:
            list_schema = self.list_schema and self.list_schema or None

        if not self.columns:
            columns = []
            for d in list_schema():
                global_search = True
                search_method = hasattr(d, "search_method") \
                    and getattr(d, "search_method") or "string_contains"
                if hasattr(d, "global_search"):
                    if d.global_search == False:
                        global_search = False

                if hasattr(d, "field"):
                    if type(d.field) == str:
                        columns.append(
                            ColumnDT(getattr(self.table, d.field),
                                     mData=d.name,
                                     global_search=global_search,
                                     search_method=search_method))
                    else:
                        columns.append(
                            ColumnDT(d.field, mData=d.name,
                                     global_search=global_search,
                                     search_method=search_method
                                     ))
                else:
                    columns.append(
                        ColumnDT(getattr(self.table, d.name),
                                 mData=d.name,
                                 global_search=global_search,
                                 search_method=search_method))
                if hasattr(d, "widget"):
                    if d.widget:
                        # _log.debug(d.widget)
                        if type(d.widget) is SelectWidget:
                            select_list[d.name] = d.widget.values

                if hasattr(d, "url"):
                    url.append(d.name)
        else:
            columns = self.columns

        query = self.db_session.query().select_from(self.table)
        list_join = kwargs.get('list_join')
        if list_join is not None:
            query = list_join(query, **kwargs)
        else:
            query = self.list_join(query, **kwargs)
        if self.req.user and self.req.user.company_id and hasattr(self.table, "company_id"):
            query = query.filter(
                self.table.company_id == self.req.user.company_id)
        list_filter = kwargs.get('list_filter')
        if list_filter is not None:
            query = list_filter(query, **kwargs)
        else:
            query = self.list_filter(query, **kwargs)

        row_table = DataTables(self.req.GET, query, columns)
        result = row_table.output_result()
        data = result and result.get("data") or {}
        for res in data:
            for k in res:
                if k in select_list.keys():
                    vals = select_list[k]
                    for r in vals:
                        if r and str(r) == str(res[k]):
                            res[k] = vals[r]
        if result.get("error"):
            _log.error(result.get("error"))
            _log.error(str(result))
            
        return result

    def not_found(self, msg=None):
        if not msg:
            msg = api_messages.NOT_FOUND
        return Response(json=msg, status=404)

    def obj2json(self, obj):
        return obj2json(obj)

    def get_bindings(self, row=None):
        """Get form bindings for the specified row."""
        return {}

    def form_validator(self, form, controls):
        """Get Validator Form"""

    def form_validate(self, form, controls):
        """Validate form"""
        try:
            data = form.validate(controls)
            return data
        except ValidationFailure as e:
            _log.error("Error validasi %s", str(e.error.asdict()))
            raise HTTPNotAcceptable(json_body=str(e.error.asdict())) from e
        
    
    def get_form(self, class_form, row=None, buttons=(btn_save, btn_cancel),
                 **kwargs):
        buttons = self.buttons and self.buttons or buttons
        if "bindings" in kwargs and kwargs["bindings"]:
            bindings = kwargs["bindings"]
        elif self.bindings:
            bindings = self.bindings
        else:
            bindings = self.get_bindings(row)

        form_params = {}

        if "validator" in kwargs and kwargs["validator"]:
            form_params["validator"] = kwargs["validator"]
        else:
            form_params["validator"] = self.form_validator

        if "after_bind" in kwargs and kwargs["after_bind"]:
            form_params["after_bind"] = kwargs["after_bind"]

        if self.form_widget:
            form_params["widget"] = self.form_widget

        schema = class_form(**form_params)
        schema = schema.bind(request=self.req, **bindings)
        schema.request= self.req
        if row:
            schema.deserialize(row)

        return Form(schema, buttons=buttons, autocomplete=self.autocomplete)

    def json_adapter(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, colander._null):
            return None
        else:
            return obj

    def success(self, data, msg=None):
        """
        Mengubah data menjadi list dan convert objek menjadi string
        """
        if not isinstance(data, list):
            data = [data]
        for i, item in enumerate(data):
            data[i] = self.obj2json(item)
        data = {"data": data}
        if msg:
            data.update(msg)
        return data

    def _get(self, request, *args, **kwargs):
        self.req = request
        if "draw" not in self.req.params:
            self.req.GET.add('draw', "1")
        if "length" not in self.req.params:
            self.req.GET.add('length', "25")
        if "start" not in self.req.params:
            self.req.GET.add('start', "0")
        return self.get_list(**kwargs)
    
    def get_custom_render(self, data):
        return data
    
    def get(self, request, *args, **kwargs):
        if self.list_permission:
            if not request.has_permission(self.list_permission):
                raise HTTPForbidden("You do not have permission to view this resource.")
            
        d = self._get(request, *args, **kwargs)
        d = self.get_custom_render(d)
        return Response(json=json.loads(json.dumps(d, default=self.json_adapter)))
    
    def post_data(self, *args, **kwargs):
        # digunakan untuk mengambil data post dari request
        try:
            data = self.req.json_body.items()

        except Exception:
            data = self.req.POST.items()
        return data
    
    def post(self, request, *args, **kwargs):
        if self.add_permission:
            if not request.has_permission(self.add_permission):
                raise HTTPForbidden("You do not have permission to add this resource.")
        self.req = request
        return self._update()

    def _update(self, id_=None):
        form = self.get_form(self.add_schema, validator=self.form_validator)
        controls = self.req.POST.items()
        try:
            controls = self.req.json_body.items()
        except Exception:
            controls = self.req.POST.items()
        data = self.form_validate(form, controls)

        # Response(json={"errors": e.error.asdict()}, status=400)
        if id_:
            row = self.table.query().get(id_)
        else:
            row = None
        user = self.user.get_by_request(self.req.user)
        row = self.table.save(data, row, user=user)
        self.db_session.add(row)
        self.db_session.flush()
        d = row.__dict__
        d.pop("_sa_instance_state", None)
        d.pop("db_session", None)
        return Response(json=self.success(d))


    def put(self, request, *args, **kwargs):
        if self.edit_permission:
            if not request.has_permission(self.edit_permission):
                raise HTTPForbidden("You do not have permission to edit this resource.")
            
        data = request.json_body
        id_ = data.get("id") or self.req.matchdict.get("id")
        if not id_:
            return HTTPBadRequest(explanation="ID is required")
        return self._update(id_)

    def delete(self, request, *args, **kwargs):
        if self.delete_permission:
            if not request.has_permission(self.delete_permission):
                raise HTTPForbidden("You do not have permission to delete this resource.")
            
        self.req = request
        data = self.req.json_body
        if "id" not in data:
            return HTTPBadRequest(explanation="ID is required")
        
        query = self.table.query().filter_by(id=data.get("id"))
        if not query.first():
            return HTTPNotFound(explanation="Data not found")
        query.delete()
        self.db_session.flush()
        self.req.session.flash("Data deleted")
        return Response(json=self.success({}, msg={"message": "Data deleted"}))
    
    
    def patch(self, data):
        self.req = data
        return self.req

    def save(self, data, user=None, obj=None):
        if not user:
            user = self.req.session.user
        if not obj:
            obj = self.table()
            obj.create_date = datetime.now()
            obj.create_uid = user and user.id or None
            obj.enabled = 1
        else:
            obj.write_date = datetime.now()
            obj.write_uid = user and user.id or None

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        self.db_session.add(obj)
        self.db_session.flush()
        return obj
