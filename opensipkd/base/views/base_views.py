import logging
import os
from datetime import datetime
from cgi import FieldStorage
from email.utils import parseaddr
from webob.multidict import MultiDict

import colander
from datatables import ColumnDT
from deform import (widget, Form, ValidationFailure, FileData, )
from deform.widget import SelectWidget
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from sqlalchemy import Table

# from opensipkd.base.views.upload import tmpstore
from opensipkd.tools.captcha import img_captcha
from opensipkd.tools import dmy, get_settings, get_ext, \
    date_from_str, get_random_string, Upload, InvalidExtension, mem_tmp_store
from opensipkd.tools.buttons import (
    btn_save, btn_cancel, btn_close, btn_delete, btn_add, btn_csv, btn_edit,
    btn_pdf, btn_upload)
# from opensipkd.tools.captcha import get_captcha
from opensipkd.tools.report import csv_response, file_response
from pyramid.request import Response
from .common import DataTables
from ..models import DBSession, Partner, Base
from ..widgets import widget_os
# , get_params, get_urls
from ..scripts.initializedb import append_csv
from ..tools import obj2json
from ...detable import DeTable
from opensipkd.base import BASE_CLASS
from pyramid.csrf import new_csrf_token, get_csrf_token

log = logging.getLogger(__name__)


class UploadSchema(colander.Schema):
    upload = colander.SchemaNode(
        FileData(),
        widget=widget.FileUploadWidget(mem_tmp_store),
        title='Unggah')


class CSRFSchema(colander.Schema):
    csrf_token = colander.SchemaNode(
        colander.String(),
        widget=widget_os.CSRFWidget(),
    )

from pyramid.interfaces import IRoutesMapper
from pyramid.threadlocal import get_current_registry

class BaseView(object):
    def __init__(self, request):
        self.req = request
        self.ses = self.req.session
        self.db_session = DBSession
        self.base = Base
        self.params = self.req.params
        self.settings = get_settings()
        self.tahun = None
#         self.bulan = None
#         self.posted = False
        self.awal = None
        self.akhir = None
        self.dt_awal = None
        self.dt_akhir = None
        self.tahun_awal = None
        self.tahun_akhir = None
#         self.departemen_kd = None
#         self.departemen_nm = None
#         self.departemen_id = None
#         self.jenis = None
        self.list_route = 'home'
#         self.list_col_defs = ""
#         self.list_cols = ""
        self.list_report = (btn_csv, btn_pdf)
        self.list_buttons = (btn_add,)
        self.list_upload = (btn_upload,)
        self.list_view_field = None
        self.columns = None
#         self.form_params = dict(scripts="")
        self.list_url = ""
        self.list_route = ''
        self.allow_view = True
        self.allow_edit = True
        self.allow_delete = True
        self.allow_post = False
        self.allow_unpost = False
        self.allow_check = False
        self.check_field = ""
        self.state_save = False
        self.server_side = True
        self.scroll_y = False
        self.scroll_x = False
        self.filter_columns = False
        self.action_suffix = "/grid/act"
        self.html_buttons = {}
        self.new_buttons = {}

        self.list_form = None  # List dam Form
        self.form_list = None  # Form kemudian detail list

        self.form_scripts = """
         $('#parent_nm').bind('typeahead:selected', function(obj, datum) {
              $('#parent_id').val(datum.id);
              $('#parent_kd').val(datum.kode);
        });"""
        self.form_widget = None

        self.list_schema = colander.Schema(
            error=colander.SchemaNode(
                colander.String, title="Override",
                missing=colander.drop,
                default="Silahkan buat list schema"))
        self.add_schema = colander.Schema(
            error=colander.SchemaNode(
                colander.String, title="Override",
                missing=colander.drop,
                default="Silahkan buat add schema"))
        self.edit_schema = colander.Schema(
            error=colander.SchemaNode(
                colander.String, title="Override",
                missing=colander.drop,
                default="Silahkan buat schema edit"))
        self.upload_schema = UploadSchema

        self.upload_exts = (".csv", ".tsv")
        self.upload_keys = ["kode"]

        self.table = Table
        self.home = self.req.home
        self.buttons = None
        self.headers = None
        self.bindings = {}
        self.autocomplete = 'on'
#         self.report_file = ""

        self.is_object = False

        self.init_session(request)
        if self.allow_check and self.allow_delete:
            self.list_buttons.append(btn_delete)

    def init_session(self, request):
        #         # if not request.user:
        #         if "g_state" in request.cookies:
        #             request.response.delete_cookie("g_state", '/')

        now = datetime.now()
        self.dt_awal = self.ses["dt_awal"] if "dt_awal" in self.ses else now
        self.awal = dmy(self.dt_awal)
        self.dt_akhir = self.ses["dt_akhir"] if "dt_akhir" in self.ses else now
        self.akhir = dmy(self.dt_akhir)
        self.ses["dt_awal"] = self.dt_awal
        self.ses["dt_akhir"] = self.dt_akhir
        self.tahun = 'tahun' in self.ses and self.ses['tahun'] \
            or now.strftime('%Y')
        self.tahun = 'tahun' in self.params and self.params['tahun'] or self.tahun
        self.ses['tahun'] = self.tahun

#         self.bulan = 'bulan' in self.ses and self.ses['bulan'] \
#             or now.strftime('%m')
#         if 'bulan' in self.params and self.params['bulan']:
#             self.bulan = self.params['bulan'].strip().zfill(2)
#             dt_awal = date_from_str(
#                 '{d}-{m}-{y}'.format(y=self.tahun, m=self.bulan, d='01'))
#             dt_akhir = dt_awal + \
#                 relativedelta(months=1) - relativedelta(days=1)
#             self.ses['awal'] = dmy(dt_awal)
#             self.ses['akhir'] = dmy(dt_akhir)

#         self.ses['bulan'] = int(self.bulan)

#         self.posted = 'posted' in self.ses and self.ses['posted'] or 0
#         if 'posted' in self.params and self.params['posted']:
#             posted = self.params['posted']
#             self.posted = ((posted == 'true' or posted == '1') and 1) or (
#                 (posted == 'false' or posted == '0') and 0) or 0
#         self.ses['posted'] = self.posted

        self.awal = 'awal' in self.ses and self.ses['awal'] or dmy(now)
        awal = 'awal' in self.params and self.params['awal'] or self.awal
        try:
            self.dt_awal = date_from_str(awal)
            self.awal = awal
        except:
            self.dt_awal = date_from_str(self.awal)

        self.ses['awal'] = self.awal
        self.ses['dt_awal'] = self.dt_awal

        self.akhir = 'akhir' in self.ses and self.ses['akhir'] or dmy(now)
        akhir = 'akhir' in self.params and self.params['akhir'] or self.akhir

        try:
            self.dt_akhir = date_from_str(akhir)
            self.akhir = akhir
        except:
            self.dt_akhir = date_from_str(self.akhir)
        self.ses['akhir'] = self.akhir
        self.ses['dt_akhir'] = self.dt_akhir

        self.tahun_awal = 'tahun_awal' in self.ses and self.ses['tahun_awal'] or self.tahun
        self.tahun_awal = 'tahun_awal' in self.params and self.params[
            'tahun_awal'] or self.tahun_awal
        self.ses['tahun_awal'] = self.tahun_awal

        self.tahun_akhir = 'tahun_akhir' in self.ses and self.ses[
            'tahun_akhir'] or self.tahun_awal
        self.tahun_akhir = 'tahun_akhir' in self.params and self.params[
            'tahun_akhir'] or self.tahun_akhir
        self.ses['tahun_akhir'] = self.tahun_akhir

        """
        self.departemen_kd = 'departemen_kd' in self.ses and self.ses[
            'departemen_kd'] or '0.0.00'
        self.departemen_nm = 'departemen_nm' in self.ses and self.ses[
            'departemen_nm'] or 'PILIH UNIT'
        self.departemen_id = 'departemen_id' in self.ses and self.ses[
            'departemen_id'] or 0
        self.ses['departemen_kd'] = self.departemen_kd
        self.ses['departemen_nm'] = self.departemen_nm
        self.ses['departemen_id'] = self.departemen_id
        if 'departemen_id' in self.params:
            self.departemen_id = self.params['departemen_id']
            if not self.departemen_id:
                self.departemen_id = 0

        self.ses["departemen_id"] = self.departemen_id
        self.jenis = 'jenis' in self.ses and self.ses['jenis'] or 0
        self.jenis = 'jenis' in self.params and self.params[
            'jenis'] or self.jenis
        self.ses['jenis'] = self.jenis
        """

    def form2dict(self, field):
        children = []
        for c in field.children:
            children.append(self.form2dict(c))
        value = hasattr(field, "cstruct") and field.cstruct or ""
        if type(value) in (colander.null, colander._null):
            value = ""
        if type(value) == dict:
            for k, v in value.items():
                if type(v) in (colander.null, colander._null):
                    value[k] = ""
        d = {
            "id": field.oid,
            "name": field.name,
            "error": {"msg": field.error and field.error.msg or ""},
            "children": children,
            "value": value
        }

        return d

    """
    def query_register(self, **kwargs):
        pass
    """

    def route_found(self, route_name):
        reg = get_current_registry()  # b/c
        mapper = reg.getUtility(IRoutesMapper)
        return mapper.get_route(route_name)
    
    def get_routes(self):
        """
        Digunakan untuk mendapatkan default url apabila list_url tidak ada
        """

    def route_list(self, **kwargs):
        """
        Digubakan untk mengalihkan proses setelah add edit view delete data
        Default akan di arahkan ke list-route untuk merubah default direction 
        """
        msg = kwargs.get("msg")
        error = kwargs.get("error", "")
        list_url = kwargs.get("list_url", self.get_routes())
        if msg:
            self.ses.flash(msg, error)

        if not list_url:
            list_url = self.req.route_url(self.list_route, **kwargs)

        log.debug(list_url)

        if self.headers:
            return HTTPFound(
                location=self.req.route_url(self.list_route),
                headers=self.headers)
        else:
            return HTTPFound(
                location=self.req.route_url(self.list_route))

    def form_validator(self, form, value):
        """Digunakan untuk memvalidasi form sebelum disubmit"""

    """
    def form_validate(self, form, err_value, **kwargs):
        controls = self.req.POST.items()
        try:
            c = form.validate(controls)
        except ValidationFailure as e:
            value = err_value()
            for f in e.field.children:
                if isinstance(f.typ, colander.Date):
                    e.cstruct[f.name] = date_from_str(
                        e.cstruct[f.name])
                if f.name == "captcha":
                    e.cstruct[f.name] = self.get_captcha_url()
            value.update(e.cstruct)
            form.set_appstruct(e.cstruct)
            return self.returned_form(form, **kwargs)
        return dict(c)

    def get_params(self, params, default=None):
        return get_params(params, default)
    """

    def get_form(self, class_form, row=None, buttons=(btn_save, btn_cancel),
                 **kwargs):
        buttons = self.buttons and self.buttons or buttons
        if "bindings" in kwargs and kwargs["bindings"]:
            bindings = kwargs["bindings"]
        elif self.bindings:
            bindings = self.bindings
        else:
            bindings = self.get_bindings(row)
        form_params = {"request": self.req}
        # form_params["after_bind"] = after_bind
        if "validator" in kwargs and kwargs["validator"]:
            form_params["validator"] = kwargs["validator"]
            # schema = class_form(validator=kwargs["validator"])
        else:
            form_params["validator"] = self.form_validator
            # schema = class_form(validator=self.form_validator)
        if "after_bind" in kwargs and kwargs["after_bind"]:
            form_params["after_bind"] = kwargs["after_bind"]
            # schema = class_form(validator=kwargs["validator"])
        if self.form_widget:
            form_params["widget"] = self.form_widget

        schema = class_form(**form_params)

        schema = schema.bind(request=self.req, **bindings)
        schema.request = self.req
        if row:
            schema.deserialize(row)

        return Form(schema, buttons=buttons, autocomplete=self.autocomplete)

    """    
    def session_failed(self, session_name):
        r = dict(form=self.req.session[session_name])
        del self.req.session[session_name]
        return r
    """

    def view_list(self, **kwargs):
        """
        custom:
            allow_view = kwargs.get("allow_view", self.allow_view)
            allow_edit = kwargs.get("allow_edit", self.allow_edit)
            allow_delete = kwargs.get("allow_delete", self.allow_delete)
            allow_post = kwargs.get("allow_post", self.allow_post)
            allow_unpost = kwargs.get("allow_unpost", self.allow_unpost)
            allow_check = kwargs.get("allow_check", self.allow_check)
            state_save = kwargs.get("state_save", self.state_save)
            filter_columns = kwargs.get("filter_columns", self.filter_columns)
            server_side = kwargs.get("server_side", self.server_side)
            new_buttons
            list_url
            action_suffix
            html_buttons
        """
        allow_view = kwargs.get("allow_view", self.allow_view)
        allow_edit = kwargs.get("allow_edit", self.allow_edit)
        allow_delete = kwargs.get("allow_delete", self.allow_delete)
        allow_post = kwargs.get("allow_post", self.allow_post)
        allow_unpost = kwargs.get("allow_unpost", self.allow_unpost)
        allow_check = kwargs.get("allow_check", self.allow_check)
        check_field = kwargs.get("check_field", self.check_field)

        state_save = kwargs.get("state_save", self.state_save)
        filter_columns = kwargs.get("filter_columns", self.filter_columns)
        if "server_side" in kwargs:
            server_side = kwargs.get("server_side")
        else:
            server_side = self.server_side
        new_buttons = kwargs.get("new_buttons")
        is_object = kwargs.get("is_object")
        list_url = kwargs.get("list_url", self.list_url)
        action_suffix = kwargs.get("action_suffix", self.action_suffix)
        list_schema = kwargs.get("list_schema", self.list_schema)
        scroll_y = kwargs.get("scroll_y", self.scroll_y)
        scroll_x = kwargs.get("scroll_x", self.scroll_x)
        html_buttons = kwargs.get("html_buttons", self.html_buttons)
        parent = kwargs.get("parent")

        kwargs.pop("allow_view", None)
        kwargs.pop("allow_edit", None)
        kwargs.pop("allow_delete", None)
        kwargs.pop("allow_post", None)
        kwargs.pop("allow_unpost", None)
        kwargs.pop("allow_check", None)
        kwargs.pop("check_field", None)
        kwargs.pop("state_save", None)
        kwargs.pop("filter_columns", None)
        kwargs.pop("server_side", None)
        kwargs.pop("new_buttons", None)
        kwargs.pop("is_object", None)
        kwargs.pop("list_url", None)
        kwargs.pop("action_suffix", None)
        kwargs.pop("list_schema", None)
        kwargs.pop("scroll_y", None)
        kwargs.pop("scroll_x", None)
        kwargs.pop("html_buttons", None)
        kwargs.pop("parent", None)

        if list_schema:
            if parent:
                action_suffix += f'?parent_id={parent.id}'

            schema = self.list_schema()
            if "bindings" in kwargs and kwargs["bindings"]:
                bindings = kwargs["bindings"]
            elif self.bindings:
                bindings = self.bindings
            else:
                bindings = self.get_bindings()

            schema = schema.bind(request=self.req, **bindings)

            if not new_buttons:
                new_buttons = self.new_buttons

            if not list_url and self.list_route:
                list_url = self.req.route_url(self.list_route)
            else:
                if list_url[:4] != 'http':
                    list_url = f"/{list_url}".replace("//", "/")
                    list_url = self.home + list_url

            table = DeTable(schema,
                            action=list_url,
                            action_suffix=action_suffix,
                            buttons=self.list_buttons,
                            request=self.req,
                            allow_view=allow_view,
                            allow_edit=allow_edit,
                            allow_delete=allow_delete,
                            allow_post=allow_post,
                            allow_unpost=allow_unpost,
                            allow_check=allow_check,
                            check_field=check_field,
                            state_save=state_save,
                            new_buttons=new_buttons,
                            filter_columns=filter_columns,
                            server_side=server_side,
                            scroll_y=scroll_y,
                            scroll_x=scroll_x,
                            html_buttons=html_buttons,
                            **kwargs
                            )
            resources = table.get_widget_resources()
            # resources=dict(css="", js="")
            if is_object:
                return dict(form=table, scripts="", css=resources["css"],
                            js=resources["js"])

            return dict(form=table.render(), scripts="", css=resources["css"],
                        js=resources["js"])

        arg = kwargs and kwargs or {}
        arg.update(url=self.list_url, col_defs=self.list_col_defs,
                   cols=self.list_cols, buttons=self.list_buttons)
        return arg

    def view_act(self, **kwargs):
        url_dict = self.req.matchdict
        if url_dict['act'] == 'grid':
            return self.get_list(**kwargs)

        elif url_dict['act'] == 'csv':
            return self.csv_response(**kwargs)

        elif url_dict['act'] == 'pdf':
            return self.pdf_response(**kwargs)

        else:
            return self.next_act(**kwargs)

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
            list_schema = self.list_schema and self.list_schema or self.form_list

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
                        log.debug(d.widget)
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

        # log.debug(str(columns))
        # qry = query.add_columns(*[c.sqla_expr for c in columns])
        # log.debug(str(qry))
        if self.req.params.get("order[0][column]") is None:
            self.req.GET.add("order[0][column]",'0')
            self.req.GET.add("order[0][dir]",'desc')

        row_table = DataTables(self.req.GET, query, columns)
        result = row_table.output_result()
        data = result and result.get("data") or {}
        for res in data:
            if self.list_view_field:
                list_url = self.req.route_url(self.list_route)
                res[self.list_view_field] = f"<a href='{list_url}/{res['id']}/view'>{res[self.list_view_field]}</a>"
            for k in res:
                if k in select_list.keys():
                    vals = select_list[k]
                    for r in vals:
                        if r and str(r) == str(res[k]):
                            res[k] = vals[r]
        #     for k, v in d.items():
        #         if k in url and v:
        #             link = "/".join([self.home, nik_url, v])
        #             d[k] =f'<a href="{link}" target="_blank">View</a>'
        return result

    def list_join(self, query, **kwargs):
        return query

    def list_filter(self, query, **kwargs):
        return query

    def next_act(self, **kwargs):
        url_dict = self.req.matchdict
        raise HTTPNotFound

    def pdf_response(self, **kwargs):
        from opensipkd.base.tools.report import jasper_export
        filename = jasper_export(self.report_file)
        return file_response(self.req, filename=filename[0])

    def csv_response(self, **kwargs):
        query = self.table.query_register()
        row = query.first()
        header = row._mapping.keys()
        rows = [list(item) for item in query.all()]
        filename = f"{get_random_string(16)}.csv"
        value = {
            'header': header,
            'rows': rows,
        }
        return csv_response(self.req, value, filename)

    def get_bindings(self, row=None):
        return {"row": row}

    def next_edit(self, form, **kwargs):
        """Digunakan untuk memproses button post yang lainnya

        Args:
            form (_type_): _description_

        Returns:
            _type_: _description_
        """
        return self.route_list(**kwargs)

    def returned_form(self, form, **kwargs):
        table = kwargs.get("table", None)
        if self.req.is_xhr and self.req.params.get("html", "false") == "false":
            data = form.cstruct
            if "captcha" in form:
                kode_captcha, file_name = img_captcha(self.req)
                self.req.session["captcha_code"] = kode_captcha
                url = self.get_captcha_url()
                cstruct = url+file_name
                data["captcha"] = cstruct
            error = kwargs.get("error", "")
            if error:
                error["data"]=data
                return self.resp_xhr({"error": error})

            return self.resp_xhr({"data": data})

        resources = form.get_widget_resources()
        readonly = "readonly" in kwargs and kwargs["readonly"] or False
        kwargs["readonly"] = readonly
        is_object = kwargs.get("is_object", self.is_object)
        kwargs.pop("table", None)
        if dict == type(table):
            resources["js"].extend(set(table["js"]) - set(resources["js"]))
            resources["css"].extend(set(table["css"]) - set(resources["css"]))
            table = table["form"]
        if is_object:

            return dict(form=form,
                        table=table and table.render() or None,
                        scripts=self.form_scripts,
                        css=resources["css"],
                        js=resources["js"],
                        **kwargs
                        )

        return dict(form=form.render(readonly=readonly),
                    table=table and table.render() or None,
                    scripts=self.form_scripts, css=resources["css"],
                    js=resources["js"],
                    **kwargs
                    )

    def view_buttons(self, row):
        result =[]
        if self.route_found(self.list_route+"-edit"):
            result.append(btn_edit)
        if self.route_found(self.list_route+"-delete"):
            result.append(btn_delete)
        result.append(btn_close)
        return tuple(result)

    def before_view(self, **kw):
        return False

    def view_view(self, **kwargs):
        request = self.req
        row = self.query_id().first()
        if not row:
            return self.id_not_found()

        self.ses["readonly"] = True
        is_object = kwargs.get("is_object", self.is_object)
        kwargs["is_object"] = is_object
        before_view = self.before_view(row=row)
        if before_view:
            return before_view
        bindings = self.get_bindings(row)
        buttons = kwargs.get("buttons", None)
        if not buttons:
            buttons = self.view_buttons(row)

        form = self.get_form(self.edit_schema, buttons=buttons,
                             bindings=bindings)
        if request.POST:
            if 'edit' in request.POST:
                return HTTPFound(
                    location=self.req.route_url(
                        self.list_route+"-edit",
                        id=row.id,
                        act='edit'))
            elif 'delete' in request.POST:
                return HTTPFound(
                    location=self.req.route_url(
                        self.list_route+"-delete",
                        id=row.id,
                        act='delete'))

            result = self.next_view(form=form, row=row)
            if result:
                return result
            return self.after_view(row=row)

        values = self.get_values(row)
        if not values:
            return self.route_list(msg="Nilai Data tidak ditemukan", error="error")
        form.set_appstruct(values)
        table = self.get_item_table(parent=row)
        kwargs["readonly"] = True
        kwargs["table"] = table
        return self.returned_form(form, **kwargs)

    def after_view(self, **kwargs):
        """Digunakan untuk customize Proses
            kwargs["row] (SQLAlchemy Row Objek):
        Returns:
            dict: (Form Objek) Secara default akan dikembalikan ke tampilan 
                Grid/List
        Notes : disini terdapat inconsistensi antara after view dan next view 
                keduanya digunakan untuk memproses aksi saat dari tampilan view
        """
        return self.route_list(**kwargs)

    def next_view(self, form=None, **kwargs):
        """Digunakan untuk customize Form Objek

        Args:
            form (Form): Objek Form,
            kwarg["row"] (SQLAlchemy Result): 

        Results:
            Form Object Or None
        """
        return

#     def set_post(self, **kwargs):
#         pass

#     def set_unpost(self, **kwargs):
#         pass

#     def view_post(self, post_field="status", **kwargs):
#         request = self.req
#         row = self.query_id().first()
#         if not row:
#             return self.id_not_found()
#         if getattr(row, post_field):
#             buttons = (btn_unpost, btn_close)
#         else:
#             buttons = (btn_post, btn_close)
#         return self.view_view(buttons=buttons)

    def view_upload(self, **kw):
        return self.view_import(**kw)

    def view_import(self, **kw):
        exts = kw.get("exts")
        table = None
        if not exts:
            exts = self.upload_exts
        from opensipkd.tools import Upload

        bindings = self.get_bindings()
        form = self.get_form(self.upload_schema, bindings=bindings)
        kw["table"] = table
        if self.req.POST:
            if 'save' in self.req.POST:
                # _here = get_params('temp_files', '/tmp')
                _here = BASE_CLASS.temp_files
                folder = os.path.join(_here, 'import')
                if not os.path.exists(folder):
                    os.makedirs(folder)

                upload = Upload(folder)
                try:
                    file_name = upload.save(self.req, "upload", exts)
                except:
                    self.ses.flash(f'File harus format {exts}', 'error')
                    return self.returned_form(form,  **kw)

                fullpath = os.path.join(folder, file_name)
                try:
                    self.save_upload(fullpath, **kw)
                except Exception as e:
                    self.req.session.flash(str(e), 'error')
                    return self.returned_form(form, **kw)

            elif "cancel" in self.req.POST or 'batal' in self.req.POST or "close" in self.req.POST:
                self.cancel_act()

            return self.route_list()
        return self.returned_form(form, **kw)

    def get_file(self, filename):
        return open(filename)

    def save_upload(self, file_name, **args):
        args.pop("table", None)
        return append_csv(self.table, file_name, self.upload_keys,
                          get_file_func=self.get_file, update_exist=True,
                          db_session=self.db_session, base=self.base,
                          **args)

    def before_add(self):
        return {}

    def validation_failure(self, value):
        """Digunakan untuk memproses validasi form yang gagal"""
        from warnings import warn
        warn("Fungsi Ini sudah tidak digunakan", DeprecationWarning)
        return value

    def cancel_act(self, **kwargs):
        return self.route_list(**kwargs)

    def after_add(self, row=None, **kwargs):
        """Digunakan untuk memproses setelah data tersimpan ke database"""
        if self.req.is_xhr:
            return self.resp_xhr({"data": {"status": "success"}})
        return self.route_list(**kwargs)

    def after_edit(self, row=None, **kwargs):
        """Digunakan untuk memproses setelah proses penyimpanan
        Args:
            row (objek, optional): Berupa objek row dari tabel yang  disimpan. 
            Defaults to None.
        Returns:
            HTTPFound: URL yang akan ditampilkan atau procedure tampilan yang lain
        """
        return self.route_list(**kwargs)

    def get_captcha_url(self):
        return self.req.static_url(BASE_CLASS.captcha_files)

    def update_value(self, value, cstruct):
        for k in cstruct:
            val = cstruct.get(k)
            if type(val) is dict:
                if k not in value:
                    value[k] = {}
                value[k] = self.update_value(value[k], val)
            elif val:
                value[k] = cstruct.get(k)
        return value

    def view_add(self, **kwargs):
        # bindings = self.get_bindings()
        form = self.get_form(self.add_schema, **kwargs)
        resources = form.get_widget_resources()
        is_object = kwargs.get("is_object", self.is_object)
        kwargs["is_object"] = is_object
        table = self.get_item_table(**kwargs)
        kwargs["table"] = table
        self.ses["readonly"] = False
        if self.req.POST:
            if 'save' in self.req.POST:
                controls = self.req.POST.items()
                if self.req.is_xhr:
                    cloned = self.req.POST.items()
                    control = []
                    for ctrl in cloned:
                        if isinstance(ctrl[1], FieldStorage):
                            control.append(
                                ("__start__", f"{ctrl[0]}:mapping"))
                            control.append(("upload", ctrl[1]))
                            control.append(("uid", ""))
                            control.append(("__end__", f"{ctrl[0]}:mapping"))
                            log.debug("Control: %s", ctrl)
                        else:
                            control.append(ctrl)
                    controls = iter(control)
                try:
                    c = form.validate(controls)
                except ValidationFailure as e:
                    value = self.before_add()
                    if self.req.is_xhr:
                        error = e.error.asdict()
                        # error.update(value)
                        # return self.resp_xhr({"error": error})
                        form.set_appstruct(e.cstruct)
                        return self.returned_form(form, error=error)

                    for f in e.field.children:
                        if isinstance(f.typ, colander.Date):
                            e.cstruct[f.name] = date_from_str(
                                e.cstruct[f.name])
                        # if f.name == "captcha":
                        #     e.cstruct[f.name] = self.get_captcha_url()
                    value = self.update_value(value, e.cstruct)
                    form.set_appstruct(value)
                    kwargs["table"] = table
                    return self.returned_form(form, **kwargs)

                values = dict(c)
                row = self.save_request(values)
                return self.after_add(row=row, **kwargs)
            elif "cancel" in self.req.POST or 'batal' in self.req.POST or "close" in self.req.POST:
                self.cancel_act()
            else:
                return self.next_add(form, resources=resources, **kwargs)

            return self.route_list(**kwargs)
        values = self.before_add()
        form.set_appstruct(values)
        kwargs["table"] = table
        return self.returned_form(form, **kwargs)

    def save(self, values, user, row=None):
        log.debug("Save")
        log.debug(values)
        values.pop("id", None)
        self.ses["old_email"] = user and user.email or None
        if not row:
            row = self.table()
            row.created = datetime.now()
            row.create_uid = user and user.id or None
        else:
            row.updated = datetime.now()
            row.update_uid = user and user.id or None

        for column in row.__table__.columns:
            if column.name in values:
                setattr(row, column.name, values[column.name])

        # for key, value in values.items():
            # if hasattr(row, key):
                # setattr(row, key, value)

        # row.from_dict(values)
        # if hasattr(row, "status"):
        #     status = "status" in values and values["status"] or 0
        #     log.debug(status)
        #     try:
        #         status = int(status)
        #     except:
        #         status = status and 1 or 0
        #
        #     log.debug(status)
        #     row.status = status
        self.db_session.add(row)
        self.after_save(values, row)
        return row

    def after_save(self, values, row):
        """Digunakan apabila ada prosess setelah melakukan penyimpanan data
           sebelum di flush ke database biasanya digunakan untuk master detail 

        Args:
            values dict: _description_
            row table: _description_
        """
        self.db_session.flush()

    def save_request(self, values, row=None):
        for k, v in self.req.GET.items():
            if k not in values:
                if v:
                    values[k] = v
        log.debug(f"Base save_request: {values}")
        return self.save(values, self.req.user, row)

    def id_not_found(self, **kwargs):
        msg = f"Data yang dicari Tidak Ditemukan ID:" \
            f" {self.req.matchdict['id']}."
        self.req.session.flash(msg, 'error')
        return self.route_list(**kwargs)

    def get_values(self, row, istime=False, null=False):
        d = dict(row.__dict__)
        d.pop('_sa_instance_state', None)
        # d = row.to_dict(null=null)
        # if 'tanggal' in d and d['tanggal']:
        #     d["tanggal"] = dmy(row.tanggal)
        values = {}
        for f in d:
            if type(d[f]) is str:
                values[f] = d[f].strip()
            else:
                if d[f] != None:
                    values[f] = d[f]

        return values

    def get_item_table(self, parent=None, **kwargs):
        if not self.form_list:
            return None
        self.list_schema = self.form_list
        kwargs["is_object"] = True
        kwargs["parent"] = parent
        return self.view_list(**kwargs)

    def before_edit(self, form):
        """
        Digunakan saat form edit ditampilkan
        :param form:
        :return: form
        """
        return form

    def edit_restrict(self, row):
        return False

    def resp_xhr(self, values):
        if values.get("data"):
            data = []
            if values and type(values["data"]) is not list:
                values["data"] = [values["data"]]
            for val in values["data"]:
                data.append(obj2json(val))
            values["data"] = data
        else:
            values["error"] = obj2json(values.get("error", {}))
        return Response(json=values)

    def view_edit(self, **kwargs):
        request = self.req
        self.ses["readonly"] = False
        row = self.query_id().first()
        is_object = kwargs.get("is_object", self.is_object)
        kwargs["is_object"] = is_object
        if not row:
            return self.id_not_found(**kwargs)

        if self.edit_restrict(row):
            return self.route_list(**kwargs)

        if not self.bindings:
            self.bindings = self.get_bindings(row)

        form = self.get_form(self.edit_schema, **kwargs)
        table = self.get_item_table(parent=row)
        kwargs["table"] = table
        values = self.get_values(row)
        if request.POST:
            if 'save' in request.POST:
                controls = request.POST.items()
                if self.req.is_xhr:
                    cloned = request.POST.items()
                    controls = []
                    for ctrl in cloned:
                        if isinstance(ctrl[1], FieldStorage):
                            controls.append(
                                ("__start__", f"{ctrl[0]}:mapping"))
                            controls.append(("upload", ctrl[1]))
                            controls.append(("uid", ""))
                            controls.append(("__end__", f"{ctrl[0]}:mapping"))
                            log.debug(f"Control: {ctrl}")
                        else:
                            controls.append(ctrl)
                    items = MultiDict(controls)
                    controls = items.items()
                    log.debug(controls)
                try:
                    controls = form.validate(controls)
                except ValidationFailure as e:
                    log.error(f"Edit Error: {str(e.error)}")
                    if self.req.is_xhr:
                        return self.resp_xhr({"error": e.error.asdict()})

                    for f in e.field.children:
                        if isinstance(f.typ, colander.Date):
                            e.cstruct[f.name] = date_from_str(
                                e.cstruct[f.name])
                        if f.name == "captcha":
                            e.cstruct[f.name] = self.get_captcha_url()
                    values = self.update_value(values, e.cstruct)
                    form.set_appstruct(values)
                    return self.returned_form(form, **kwargs)

                c = dict(controls)
                self.save_request(c, row)
                if self.req.is_xhr:
                    return self.resp_xhr({"data": [c]})

                return self.after_edit(row=row, **kwargs)

            return self.next_edit(form, row=row)

        # if self.req.is_xhr:
        #     return self.resp_xhr({"data": [form.cstruct]})
        form.set_appstruct(values)

        form = self.before_edit(form)

        return self.returned_form(form, **kwargs)

    def delete_msg(self, row):
        return f'Data ID {row.id} sudah dihapus.'

    def before_delete(self, row):
        """Digunakan untuk memproses sebelum data dihapus
        Args: row (objek): Berupa objek row dari tabel yang akan dihapus datanya.
        Returns: Exception: Apabila ada akan menolak pennghapusan data atau gagal
                            apabila proses ada yang salah 
                 None: Apabila proses berhasil

        """

    def view_delete(self, **kwargs):
        request = self.req
        
        q = self.query_id()
        if self.allow_check:
            q=self.query_delete()
            rcount=q.count()
            try:
                q.delete(synchronize_session='fetch')
                self.db_session.flush()
                request.session.flash(f"{rcount} Data berhasil dihapus.")
            except Exception as e:
                request.session.flash(
                    f"Gagal menghapus data. "
                    f"Pastikan data tidak berelasi dengan data lain. "
                    f"Error: {str(e)}", "error")
            return self.route_list()
        
        self.ses["readonly"] = True
        row = q.first()
        is_object = kwargs.get("is_object", self.is_object)
        kwargs["is_object"] = is_object
        if not row:
            return self.id_not_found()
        if not self.bindings:
            self.bindings = self.get_bindings(row)
        if request.POST:
            if 'delete' in request.POST:
                msg = self.delete_msg(row)
                try:
                    self.before_delete(row)
                except Exception as e:
                    self.ses.flash(e, "error")
                    return self.route_list()

                q.delete()
                self.db_session.flush()
                request.session.flash(msg)
            return self.route_list()
        form = self.get_form(
            self.edit_schema, buttons=(btn_delete, btn_cancel))
        table = self.get_item_table(parent=row)

        resources = form.get_widget_resources()
        form.set_appstruct(self.get_values(row))
        kwargs["readonly"] = True
        kwargs["table"] = table
        return self.returned_form(form, **kwargs)
    
    def query_delete(self):
        id_ = self.req.matchdict['id']
        if id_ == 'all':
            ids_ = [int(i) for i in self.req.params.get("ids").split(",")]
            return self.table.query().filter(self.table.id.in_(ids_))
        return self.table.query_id(id_)


    def query_id(self, id_=None):
        id_ = id_ or self.req.matchdict['id']
        return self.table.query_id(id_)

        # if self.req.user:
        #     if hasattr(self.table, 'company_id') and self.req.user.company_id:
        #         q = q.filter_by(company_id=self.req.user.company_id)
        # return q

#     def filter_company(self, query):
#         if self.req.user.company_id:
#             return query.filter(
#                 self.table.company_id == self.req.user.company_id)
#         return query

    def next_add(self, form, **kwargs):
        """
        Digunakan untuk memverifikasi button yang lainnya
        :param form:  Object Form
        :return:
        """
        return self.route_list()

#     def convert_avi_to_mp4(self, input_name):
#         output = os.path.splitext(input_name)[0] + ".mp4"
#         command = "ffmpeg -y -i {input}  -c:v mpeg4 {output}".format(
#             input=input_name, output=output)
#         log.debug(f"Convert: {command}")
#         os.popen(command)
#         # os.remove(input_name)
#         # "ffmpeg -i {input} -ac 2 -b:v 2000k -c:a aac -c:v libx264 -b:a 160k -vprofile high -bf 0 -strict experimental -f mp4 {output}.mp4"
#         return output

#     def form_error(self, form, error=None):
#         if error is None:
#             error = []

#         if not error:
#             return

#         err = colander.Invalid(form, "")
#         for e in error:
#             err[e[0]] = e[1]
#         raise err

#     def save_upload_file(self, form, value, folder, field):
#         file_dict = value[field]["file_name"]
#         if not os.path.exists(folder):
#             os.makedirs(folder)
#         upload = Upload(folder)
#         error = []
#         if file_dict:
#             input_file = file_dict["fp"]
#             if input_file:
#                 filename = file_dict["filename"].lower()
#                 ext = get_ext(filename)
#                 if ext not in self.upload_exts:
#                     error.append(
#                         (field, InvalidExtension(self.upload_exts).error))
#                 else:
#                     full_file_name = upload.save_to_file(
#                         input_file, ext, filename)
#                     if ext == ".avi":
#                         full_file_name = self.convert_avi_to_mp4(
#                             full_file_name)
#                     file_name = os.path.split(full_file_name)[1]
#                     return file_name

#         self.form_error(form, error)

    def save_file(self, values, field, path=None, filename=None):
        """digunakan untuk menyimpan file upload dari form
        Args:
        
        """
        if field in values and values[field]:
            value = values[field]
            file_name = value["filename"]
            ext = get_ext(file_name)
            if ext not in self.upload_exts:
                raise InvalidExtension(self.upload_exts)

            if "fp" in value and value["fp"] and value["fp"] != b'':
                if not path:
                    path = BASE_CLASS.temp_files
                    path = os.path.join(path, "upload")

                if not os.path.exists(path):
                    os.makedirs(path)
                upload = Upload(path)
                resp = upload.save_fp(value)
                if filename:
                    ext = get_ext(resp)
                    new_resp = filename+ext
                    new_resp_full = os.path.join(path, new_resp)
                    if os.path.isfile(new_resp_full):
                        os.remove(new_resp_full)

                    os.rename(os.path.join(path, resp), new_resp_full)
                    return new_resp
                return resp
            return value["filename"]

    def get_partner(self):
        return Partner.query_email(self.req.user.email).first()


@colander.deferred
def deferred_status(node, kw):
    values = kw.get('daftar_status', [])
    return widget.SelectWidget(values=values)


def email_validator(node, value):
    name, email = parseaddr(value)
    if not email or email.find('@') < 0:
        raise colander.Invalid(node, 'Invalid email format')


"""






# class Store(dict):
#     def preview_url(self, name):
#         return ""


# username_re = re.compile('^[a-z0-9_]{6,16}$', re.IGNORECASE)


# def user_name_validator(node, value):
#     if not username_re.match(value):
#         raise colander.Invalid(
#             node,
#             'Value must be between 6 and 16 characters and can only contain ' +
#             'uppercase and lowercase alphanumeric characters or an underscore')


# def need_captcha():
#     is_captcha = get_params("reg_captcha")
#     return is_captcha == '1' or is_captcha == "True" or is_captcha == "true" \
#         or is_captcha == True


# def need_verify():
#     result = get_params("reg_verify")
#     return result == '1' or result == "True" or result == "true" or result == True


# def get_url_captcha(request):
#     captcha = get_captcha(request)
#     return os.path.join(get_urls(request.route_url('home')), 'captcha', captcha)
"""
