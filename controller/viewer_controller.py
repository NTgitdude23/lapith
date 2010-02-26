# Nessus results viewing tools
#
# Developed by Felix Ingram, f.ingram@gmail.com, @lllamaboy
# http://www.github.com/nccgroup/nessusviewer
#
# Released under AGPL. See LICENSE for more information

import wx
import os
from model.Nessus import NessusFile, NessusTreeItem, MergedNessusReport, NessusReport, NessusItem
import difflib
from drop_target import MyFileDropTarget
from view import (
        ViewerView,
        SaveDialog,
        ID_Load_Files,
        ID_Merge_Files,
        ID_Generate_CSV,
        ID_About,
        )
from  wx.lib.wordwrap import wordwrap
import csv

ID_Save_Results = wx.NewId()

class ViewerController:
    def __init__(self):
#    def initView(self):
        self.view = ViewerView()

        ## Instance vars
        self.files = []
        self.tests = []
        self.tree_hooks = {}

        ## Dialog paths
        self._save_path = os.getcwd()
        self._open_path = os.getcwd()

        self.create_tree()
        drop_target = MyFileDropTarget(self.view.tree,
                {
                    "nessus": self.drop_action,
                },
                self.view.display.write
                )
        self.view.tree.SetDropTarget(drop_target)

        self.bind_events()
        self.view.Layout()
        self.view.Show()

    def drop_action(self, file_):
        self.files.append(NessusFile(file_))
        self.create_scan_trees()

    def add_output_page(self, title, text, font="Courier New"):
        display = self.view.CreateTextCtrl(font=font)
        display.SetValue(text)
        self.delete_page_with_title(title)
        self.view.notebook.AddPage(display, title)
        return self.view.notebook.GetPageIndex(display)

    def load_files(self, event):
        wildcard = "Nessus files (*.nessus)|*.nessus|"     \
                   "All files (*.*)|*.*"

        dlg = wx.FileDialog(
                self.view, message="Choose a file",
                defaultDir=os.getcwd(),
                defaultFile="",
                wildcard=wildcard,
                style=wx.OPEN | wx.MULTIPLE | wx.CHANGE_DIR
                )
        if dlg.ShowModal() == wx.ID_OK:
            # This returns a Python list of files that were selected.
            paths = dlg.GetPaths()

            if paths:
                for path in paths:
                    self.files.append(NessusFile(path))
                self._open_path = paths[0].rsplit(os.sep, 1)[0]
        dlg.Destroy()
        self.create_scan_trees()

    def delete_page_with_title(self, title):
        notebook = self.view.notebook
        page_count = notebook.GetPageCount()
        for i in xrange(page_count):
            if notebook.GetPageText(i) == title:
                notebook.DeletePage(i)

    def create_tree(self):
        self.view.tree.DeleteAllItems()
        self.view.tree.AddRoot("Scans")

        self.create_scan_trees()
        self.view.tree.Expand(self.view.tree.GetRootItem())

    def create_scan_trees(self):
        scans = self.view.tree.GetRootItem()
        self.view.tree.DeleteChildren(scans)

        for file_ in self.files:
            self.create_scan_tree(file_, scans)
        self.view.tree.Expand(scans)

    def sorted_tree_items(self, report, items):
        list_ = list(set([NessusTreeItem(report, i) for i in items]))
        list_.sort()
        return list_
        
    def create_scan_tree(self, file_, hosts):
        reports = file_.get_all_reports()
        scans_hook = self.view.tree.GetRootItem()
        file_hook = self.view.tree.AppendItem(scans_hook, file_.short_name, 0)

        for report in reports:
            scan = self.view.tree.AppendItem(file_hook, report.reportname, 0)
            self.view.tree.SetPyData(scan, report)

            info = self.view.tree.AppendItem(scan, "Info", 0)
            self.view.tree.SetPyData(info, report.info)

            if report.policy:
                policy = self.view.tree.AppendItem(scan, "Policy", 0)
                self.view.tree.SetPyData(policy, report.policy)

            hosts = self.view.tree.AppendItem(scan, "Hosts", 0)
            self.view.tree.SetPyData(hosts, "\n".join(str(h) for h in report.hosts))

            items_hook = self.view.tree.AppendItem(scan, "Findings", 0)
            self.view.tree.SetPyData(items_hook, self.sorted_tree_items(report, report.highs+report.meds+report.lows+report.others))
            high_hook = self.view.tree.AppendItem(items_hook, "Highs", 0)
            self.view.tree.SetPyData(high_hook, self.sorted_tree_items(report, report.highs))
            med_hook = self.view.tree.AppendItem(items_hook, "Meds", 0)
            self.view.tree.SetPyData(med_hook, self.sorted_tree_items(report, report.meds))
            low_hook = self.view.tree.AppendItem(items_hook, "Lows", 0)
            self.view.tree.SetPyData(low_hook, self.sorted_tree_items(report, report.lows))
            other_hook = self.view.tree.AppendItem(items_hook, "Others", 0)
            self.view.tree.SetPyData(other_hook, self.sorted_tree_items(report, report.others))
            for high in self.sorted_tree_items(report, report.highs):
                item = self.view.tree.AppendItem(high_hook, str(high), 0)
                self.view.tree.SetPyData(item, high)
            for med in self.sorted_tree_items(report, report.meds):
                item = self.view.tree.AppendItem(med_hook, str(med), 0)
                self.view.tree.SetPyData(item, med)
            for low in self.sorted_tree_items(report, report.lows):
                item = self.view.tree.AppendItem(low_hook, str(low), 0)
                self.view.tree.SetPyData(item, low)
            for other in [NessusTreeItem(report, o) for o in report.others]:
                item = self.view.tree.AppendItem(other_hook, str(other), 0)
                self.view.tree.SetPyData(item, other)

    def get_item_output(self, item):
        hosts = item.report.hosts_with_pid(item.pid)

        initial_output = hosts[0].plugin_output(item.pid)
        diffs = []
        for host in hosts[1:]:
            diff = difflib.unified_diff(initial_output.splitlines(), host.plugin_output(item.pid).splitlines())
            diffs.append((host, "\n".join(list(diff))))
        initial_output = item.name.strip() + "\n\n" + initial_output

        diff_output = ""

        identical_hosts = [hosts[0]]
        for (host, diff) in diffs:
            if diff:
                diff_output += "=" * 70 + "\n\n%s\n%s\n\n" % (host, diff)
            else:
                identical_hosts.append(host)
        output = item.name+"\n"
        output += "%s hosts with this issue\n" % len(hosts)
        output += "\n".join(str(i).split()[0] for i in hosts)
        output += "\n"+"-"*20+"\n"
        output += "\n".join(str(i) for i in identical_hosts) + "\n\n" + initial_output
        return output, diff_output

    def show_nessus_item(self, item):
        output, diff_output = self.get_item_output(item)

        diff_title = "Diffs"
        self.delete_page_with_title(diff_title)

        display = self.view.display
        if diff_output:
            self.add_output_page(diff_title, diff_output, font="Courier New")
        display.SetValue(output)

    def generate_csv(self, event):
        saveas = SaveDialog(self.view, defaultDir=self._save_path, message="Save csv as...").get_choice()
        if saveas:
            merged_scans = MergedNessusReport(self.files)
            if not saveas.endswith(".csv"):
                saveas = saveas+".csv"
            sorted_tree_items = self.sorted_tree_items(merged_scans, merged_scans.highs+merged_scans.meds+merged_scans.lows+merged_scans.others)
            serverity = {0:"Other", 1:"Low", 2:"Med", 3:"High"}
            with open(saveas, "wb") as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(["PID","Severity","Hosts","Output","Diffs"])
                for item in sorted_tree_items:
                    csv_writer.writerow([
                        item.pid,
                        serverity[item.item.severity],
                        "\n".join(x.address for x in merged_scans.hosts_with_pid(item.pid)),
                        self.get_item_output(item)[0],
                        self.get_item_output(item)[1],
                        ]
                        )

    def combine_files(self, event):
        scans_hook = self.view.tree.GetRootItem()
        merged_scans = MergedNessusReport(self.files)

        if merged_scans.get_all_reports():
            merge_hook = self.view.tree.AppendItem(scans_hook, "Merged Files", 0)

            items_hook = self.view.tree.AppendItem(merge_hook, "Findings", 0)
            self.view.tree.SetPyData(items_hook, self.sorted_tree_items(merged_scans, merged_scans.highs+merged_scans.meds+merged_scans.lows+merged_scans.others))

            high_hook = self.view.tree.AppendItem(items_hook, "Highs", 0)
            self.view.tree.SetPyData(high_hook, self.sorted_tree_items(merged_scans, merged_scans.highs))

            med_hook = self.view.tree.AppendItem(items_hook, "Meds", 0)
            self.view.tree.SetPyData(med_hook, self.sorted_tree_items(merged_scans, merged_scans.meds))

            low_hook = self.view.tree.AppendItem(items_hook, "Lows", 0)
            self.view.tree.SetPyData(low_hook, self.sorted_tree_items(merged_scans, merged_scans.lows))

            other_hook = self.view.tree.AppendItem(items_hook, "Others", 0)
            self.view.tree.SetPyData(other_hook, self.sorted_tree_items(merged_scans, merged_scans.others))

            for high in self.sorted_tree_items(merged_scans, merged_scans.highs):
                item = self.view.tree.AppendItem(high_hook, str(high), 0)
                self.view.tree.SetPyData(item, high)
            for med in self.sorted_tree_items(merged_scans, merged_scans.meds):
                item = self.view.tree.AppendItem(med_hook, str(med), 0)
                self.view.tree.SetPyData(item, med)
            for low in self.sorted_tree_items(merged_scans, merged_scans.lows):
                item = self.view.tree.AppendItem(low_hook, str(low), 0)
                self.view.tree.SetPyData(item, low)
            for other in merged_scans.others:
                item = self.view.tree.AppendItem(other_hook, str(other), 0)
                self.view.tree.SetPyData(item, other)
            self.view.tree.Expand(scans_hook)

    def bind_events(self):
        # Toolbar events
        self.view.Bind(wx.EVT_TOOL, self.load_files, id=ID_Load_Files)
        self.view.Bind(wx.EVT_TOOL, self.combine_files, id=ID_Merge_Files)
        self.view.Bind(wx.EVT_TOOL, self.generate_csv, id=ID_Generate_CSV)
        # Tree clicking and selections
        self.view.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_sel_changed, self.view.tree)
        self.view.tree.Bind(wx.EVT_TREE_ITEM_MENU, self.on_right_click, self.view.tree)
        # Tab close event - will prevent closing the output tab
        self.view.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CLOSE, self.on_page_close)
        # Menu stuff
        self.view.Bind(wx.EVT_MENU, self.load_files, id=wx.ID_OPEN)
        self.view.Bind(wx.EVT_MENU, self.extract_results, id=ID_Save_Results)
        self.view.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)

    def extract_results(self, event):
        item = self.view.tree.GetSelection()
        data = self.view.tree.GetItemData(item).GetData()

        saveas = SaveDialog(self.view, defaultDir=self._save_path, message="Save results as...").get_choice()
        if saveas:
            with open(saveas, "w") as f:
                output = ""
                if isinstance(data, list):
                    for item in data:
                        output, diff_output = self.get_item_output(item)
                        f.write("="*20+"\n")
                        f.write(output)
                        f.write(diff_output)
                elif isinstance(data, NessusReport):
                    pass
                elif isinstance(data, MergedNessusReport):
                    pass

    def on_right_click(self, event):
        item = event.GetItem()
        self.view.tree.SelectItem(item)
        data = self.view.tree.GetItemData(item).GetData()
        if isinstance(data, NessusReport) or isinstance(data, MergedNessusReport) or isinstance(data, list):
            menu = wx.Menu()
            menu.Append(ID_Save_Results, "Save all results")
            self.view.PopupMenu(menu)
            menu.Destroy()

    def on_page_close(self, event):
        idx = event.GetSelection()
        tab = event.GetEventObject().GetPage(idx)
        if tab == self.view.display:
            event.Veto()

    def on_sel_changed(self, event):
        item = event.GetItem()
        tree = self.view.tree
        data = tree.GetItemData(item).GetData()
        if isinstance(data, NessusReport):
            self.view.display.Clear()
            self.view.display.SetValue(data.reportname)
            self.view.notebook.SetSelection(0)
            self.view.tree.SetFocus()
        elif isinstance(data, NessusItem):
            self.view.display.Clear()
            self.view.display.SetValue(data.output.replace('\\n', "\n"))
            self.view.notebook.SetSelection(0)
            self.view.tree.SetFocus()
        elif isinstance(data, NessusTreeItem):
            self.show_nessus_item(data)
            self.view.tree.SetFocus()
        elif isinstance(data, str):
            self.view.display.Clear()
            self.view.display.SetValue(data.replace('\\n', "\n"))
            self.view.notebook.SetSelection(0)
            self.view.tree.SetFocus()

    def on_exit(self, event):
        self.view.Close()

    def on_about(self, event):
        ## Just display a dialog box
        info = wx.AboutDialogInfo()
        info.Name = "Nessus Results - The right way around"
        info.Version = "1.0.0\n"
        info.Copyright = "(C) 2010 Felix Ingram\n"
        info.Description = wordwrap(
                "Sometimes you need Nessus results on a per-issue basis, "
                "sometimes you need to combine a load of reports into one."
                "\n\nUncon only edition - keep it in the family people.",
            350, wx.ClientDC(self.view))
        info.Developers = [ "Felix Ingram",]
        ## Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)
