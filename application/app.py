#TODO: generalize code to allow for text files (and possibly other types)
#TODO: settings w/JSON file that loads in saved attributes

#from sys import displayhook
import tkinter as tk
from tkinter import *
from tkinter import (ttk, filedialog as fd)

#from pygments import highlight
from tableDisplayCSV import TableDisplayCSV
from termDisplay import TermDisplayFrame
from dataFileGroupDisplay import FileGroupFrame
from wrapperLabel import WrapperLabel

from tokenClass import Token
from dataFile import DataFile
from dataFileGroup import DataFileGroup
from generalized_redacting import run_redaction_full,PROB_ROUNDING

import pandas as pd

from PIL import Image, ImageTk, ImageSequence

import threading, time

import os  # for creating new directories if needed

import numpy as np
import math

TOOL_NAME = 'MARI'

VIEW_ROW_LIMIT = 20
VIEW_TERM_LIMIT = 10
from labels_and_feats import IDABLE_LABEL_LIST,LABEL_LIST
REDACTION_CATEGORIES = list(LABEL_LIST)
INFO_HEADERS = ['Original Token','Replacement','Occurrences Redacted','Average Sensitivity','perc','num_red','Token Category','show']


"""
This keeps track of custom tokens we want to redact (user input in app)
"""
class CustomRedactionsList():
    def __init__(self):
        # TODO: value is a struct s.t. [count,replacement_val]
        self.custom_tokens = dict({})
        self.names_only = []  # essentially keys of dictionary
        self.count = 0  # length of names_only
    def __str__(self):
        return str(self.names_only)


"""
This class just keeps track of the little timeline that we have at the top
"""
class TimelineHeader(ttk.Frame):
    def __init__(self,master=None):
        ttk.Frame.__init__(self, master)
        self.pack(fill='x',anchor='center')

        self.raw_width = 0.2 * self.winfo_screenwidth()
        #print(self.raw_width)
        self.label_width = 20 #math.floor(self.raw_width)

        # timeline colors
        self.bg_selected = 'orange'
        self.fg_selected = 'white'
        self.bg_unselected = '#fce5cd'
        self.fg_unselected = '#ff9900'

        self.imp_text = 'Import data'
        self.import_label = ttk.Label(self,text=self.imp_text,width=self.label_width,anchor='center')
        self.import_label['background'] = self.bg_selected
        self.import_label['foreground'] = self.fg_selected

        self.set_text = 'Redaction scope'
        self.settings_label = ttk.Label(self,text=self.set_text,width=self.label_width,anchor='center')
        self.settings_label['background'] = self.bg_unselected
        self.settings_label['foreground'] = self.fg_unselected

        self.red_text = 'Review and revise'
        self.review_label = ttk.Label(self,text=self.red_text,width=self.label_width,anchor='center')
        self.review_label['background'] = self.bg_unselected
        self.review_label['foreground'] = self.fg_unselected

        self.exp_text = 'Export data'
        self.export_label = ttk.Label(self,text=self.exp_text,width=self.label_width,anchor='center')
        self.export_label['background'] = self.bg_unselected
        self.export_label['foreground'] = self.fg_unselected

        self.current_step = self.import_label

        self.import_label.grid(row=0,column=0, padx=5, pady=5)
        self.settings_label.grid(row=0,column=1, padx=5, pady=5)
        self.review_label.grid(row=0,column=2, padx=5, pady=5)
        self.export_label.grid(row=0,column=3, padx=5, pady=5)


    def swap_active_color(self,lbl):  # visual indicator of which step we are on
        self.current_step['background'] = self.bg_unselected
        self.current_step['foreground'] = self.fg_unselected
        self.current_step = lbl
        self.current_step['background'] = self.bg_selected
        self.current_step['foreground'] = self.fg_selected


    def next_step(self):  # change display: next step in timeline
        txt = self.current_step['text']
        if(txt == self.imp_text):
            self.swap_active_color(self.settings_label)
        elif(txt == self.set_text):
            self.swap_active_color(self.review_label)
        elif(txt == self.red_text):
            self.swap_active_color(self.export_label)


    def prev_step(self):  # change display: previous step in timeline
        txt = self.current_step['text']
        if(txt == self.set_text):
            self.swap_active_color(self.import_label)
        elif(txt == self.red_text):
            self.swap_active_color(self.settings_label)
        elif(txt == self.exp_text):
            self.swap_active_color(self.review_label)



"""
This is the bulk of the app, where everything runs. Each page has its own
function, so it's semi-modular, but it could definitely be cleaned up and made
more malleable.
"""
class RedactingTool(ttk.Frame):
    def __init__(self, master=None):
        self.tok_list = []
        self.file_list = []
        self.group_list = []
        self.export_dir_list = []
        tok_cats = list(REDACTION_CATEGORIES + ['Non-identifiable'])  # TODO: potentially ignore non-identifiable terms?
        self.token_buckets = dict.fromkeys(tok_cats,list([]))

        self.terms_redact_custom = CustomRedactionsList()
        self.terms_to_ignore = CustomRedactionsList()

        # temp structures to store redacted columns and just tokens that were replaced
        self.tokenized_data = []
        self.replacement_data = []

        self.continue_flag = False

        self.show_redactions = False

        self.redaction_categories = list(REDACTION_CATEGORIES)
        self.redaction_categories_dict = {}
        for i in range(len(self.redaction_categories)):
            self.redaction_categories_dict[i] = self.redaction_categories[i]
        #print(self.redaction_categories_dict)

        self.redaction_threshold = tk.DoubleVar(value=0.5)

        #basic window parameters, widgets
        #ttk.Frame.__init__(self, master)
        tk.Frame.__init__(self, master)
        master.minsize(width=500, height=500)  # make only fullscreen or allow changes to window size parameter
        #master.maxsize(width=900, height=900)
        master.title(TOOL_NAME)  # tool name
        master.state('zoomed')  # added for starting in fullscreen

        self.win_height = self.winfo_screenheight()
        self.win_width = self.winfo_screenwidth()

        # dark mode babey
        #style = ttk.Style(self)
        self.tk.call('source', r'style/azure.tcl')
        #style.theme_use('azure_dark')
        self.tk.call("set_theme", "dark")

        self.pack()
        self.grid_rowconfigure(1,weight=1)
        self.grid_columnconfigure(0,weight=1)

        # create timeline to keep track of where user is in process
        self.timeline_container = ttk.Frame(self)
        self.timeline = TimelineHeader(self.timeline_container)
        self.timeline_container.grid(column=0,row=0,sticky='EW',padx=5)

        # frames for everything else
        # main big container
        self.frame_container = ttk.Frame(self)
        self.frame_container.grid(column=0,row=1,sticky='NESW')
        CONTAINER_SIZE = (0.6 * self.win_height)
        self.frame_container.grid_rowconfigure(1,weight=1,minsize=CONTAINER_SIZE)
        self.frame_container.grid_columnconfigure(0,weight=1)

        # instructions/context container (contains info abt current step)
        self.context_container = ttk.Frame(self.frame_container)
        self.context_container.grid(column=0,row=0,sticky='EW')

        # display container (contains group info, previews, etc.)
        self.display_container = ttk.Frame(self.frame_container)
        self.display_container.grid(column=0,row=1,sticky='NESW',padx=5,pady=5)

        self.display_container.grid_columnconfigure(0,weight=1)
        RIGHT_SIZE = (0.6 * self.win_width)
        self.display_container.grid_columnconfigure(1,weight=4,minsize=RIGHT_SIZE)
        self.display_container.grid_rowconfigure(0,weight=1)

        # split screen for viewing purposes
        self.left_container = ttk.Frame(self.display_container)
        self.right_container = ttk.Frame(self.display_container)

        self.left_container.grid(column=0,row=0,sticky='NESW',padx=5)
        self.right_container.grid(column=1,row=0,sticky='NESW')

        self.left_container.grid_columnconfigure(0,weight=1)
        self.left_container.grid_rowconfigure(0,weight=1)

        self.right_container.grid_columnconfigure(0,weight=1)
        self.right_container.grid_rowconfigure(1,weight=1)

        # results tabs view
        self.result_tabs_container = ttk.Frame(self.right_container)
        self.result_tabs_container.grid(column=0,row=0,sticky='NESW')

        # frame for previewing files, showing results
        self.preview_container = ttk.Frame(self.right_container)
        self.preview_container.grid(column=0,row=1,sticky='NESW')
        # self.preview_container.grid_rowconfigure(0, weight=1)
        # self.preview_container.grid_columnconfigure(0, weight=1)

        # scrollbars
        ##################################
        # left container should be scrollable both directions
        self.left_canvas = tk.Canvas(self.left_container)
        self.left_scrollable_container = ttk.Frame(self.left_canvas)
        self.left_v_scroll = ttk.Scrollbar(self.left_container,orient="vertical",command=self.left_canvas.yview)
        self.left_h_scroll = ttk.Scrollbar(self.left_container,orient="horizontal",command=self.left_canvas.xview)
        self.prev_frame_id = self.left_canvas.create_window((0,0), window=self.left_scrollable_container,anchor='nw',tags="canvas_tag")

        self.left_canvas.configure(yscrollcommand=self.left_v_scroll.set)
        self.left_canvas.configure(xscrollcommand=self.left_h_scroll.set)

        self.left_canvas.grid_rowconfigure(0, weight=1)
        self.left_canvas.grid_columnconfigure(0, weight=1)

        self.left_scrollable_container.grid_rowconfigure(0, weight=1)
        self.left_scrollable_container.grid_columnconfigure(0, weight=1)


        # self.left_h_scroll.grid(row=2,sticky='EW')
        # self.left_v_scroll.grid(row=1,column=2,sticky='NS')
        self.left_h_scroll.pack(side='bottom',fill='x')
        self.left_v_scroll.pack(side='right',fill='y')
        self.left_canvas.pack(side='left',fill='both',expand=True)

        self.left_canvas.bind(
            "<Configure>",
            lambda e: self.on_canvas_config(
                self.left_scrollable_container,e, self.left_canvas, 'frame'
            )
        )
        self.left_scrollable_container.bind("<Configure>",
            lambda e: self.on_frame_config(
                self.left_scrollable_container,e, self.left_canvas, 'canvas_tag'
            )
        )

        ##################################
        # preview container should be scrollable both directions
        CANVAS_WIDTH = 750
        self.preview_canvas = tk.Canvas(self.preview_container,width=CANVAS_WIDTH)
        self.preview_scrollable_container = ttk.Frame(self.preview_canvas)
        self.v_scroll = ttk.Scrollbar(self.right_container,orient="vertical",command=self.preview_canvas.yview)
        self.h_scroll = ttk.Scrollbar(self.right_container,orient="horizontal",command=self.preview_canvas.xview)
        self.prev_frame_id = self.preview_canvas.create_window((0,0), window=self.preview_scrollable_container,anchor='nw',tags="canvas_tag")

        self.preview_canvas.configure(yscrollcommand=self.v_scroll.set)
        self.preview_canvas.configure(xscrollcommand=self.h_scroll.set)
        #self.preview_canvas.bind('<MouseWheel>',self.scroll)

        self.preview_canvas.grid_rowconfigure(0, weight=1)
        self.preview_canvas.grid_columnconfigure(0, weight=1)

        self.preview_scrollable_container.grid_rowconfigure(0, weight=1)
        self.preview_scrollable_container.grid_columnconfigure(0, weight=1)

        self.preview_canvas.pack(side='left',fill='both',expand=True)
        self.h_scroll.grid(row=2,sticky='EW')
        self.v_scroll.grid(row=1,column=2,sticky='NS')

        self.preview_canvas.bind(
            "<Configure>",
            lambda e: self.on_canvas_config(
                self.preview_scrollable_container,e, self.preview_canvas, 'frame'
            )
        )
        self.preview_scrollable_container.bind("<Configure>",
            lambda e: self.on_frame_config(
                self.preview_scrollable_container,e, self.preview_canvas, 'canvas_tag'
            )
        )

        '''
        # tabs container should be scrollable in x direction
        '''

        # back/continue container (contains the buttons to move between steps)
        self.button_container = ttk.Frame(self.frame_container)
        self.button_container.grid(column=0,row=2,padx=5,pady=5)


        self.tabs_statuses = dict({})

        self.select_files_page()


    def on_frame_config(self,container,e=None,widget=None,tag=''):
        container.update_idletasks()
        widget.configure(scrollregion=widget.bbox(tag))

    def on_canvas_config(self,container,e,widget=None,tag=''):
        minWidth = container.winfo_reqwidth()
        minHeight = container.winfo_reqheight()

        if self.winfo_width() >= minWidth:
            newWidth = self.winfo_width()
        else:
            newWidth = minWidth

        if self.winfo_height() >= minHeight:
            newHeight = self.winfo_height()
        else:
            newHeight = minHeight

        widget.itemconfig(tag,width=newWidth,height=newHeight)


    def clear_frame(self,frame):
        for widget in frame.winfo_children()[1:]:
            try:
                widget.grid_forget()
            except:
                widget.forget()


    """
    file selection through file dialog, upload file to be redacted
    """
    def upload_file(self,event=None):  #needs to update combobox for additional files
        fnames = fd.askopenfilenames(filetypes=[('CSV Files', '.csv'),('Text Files', '.txt')])  # ensures that the user can only select csv/txt files (for now, can add more later)
        fnames_lst = list(fnames)

        if(fnames_lst == []):
            return

        self.upload_button["text"] = "Add more file(s)"

        self.context_labels = []

        idx = 0
        for n_file in fnames_lst:
            existing_file_flag = False
            end_fname = n_file.split('/')[-1]
            for curr_file in self.file_list:
                if(end_fname == curr_file.get_name()):
                    existing_file_flag = True
                    break
            if(not existing_file_flag):
                # offer choice to remove file
                rem_str = 'Remove ' + end_fname + ' from files to be redacted'

                # init DataFile object
                new_file = DataFile(fname=end_fname,fpath=n_file)

                # add button and label to scrollable frame
                new_file.remove_button = ttk.Button(self.result_tabs_container,text=rem_str,\
                command=lambda n_file=n_file:self.remove_file(new_file))

                temp_label = ttk.Label(self.context_container, text=n_file)  # self.scrollable_frame
                new_file.context_label = temp_label

                self.file_list.append(new_file)

                # update dropdown menu also
                if(hasattr(self,'file_drop_menu')):
                    self.file_drop_menu['values'] = [dfile.get_name() for dfile in self.file_list]
                    self.options = [(n_file.get_name()) for n_file in self.file_list]
                    self.options.insert(0,'(Select a File to Preview)')


        #Initializes and updates the file grouping frame
        if not hasattr(self,'file_group_frame'):
            self.file_group_frame = FileGroupFrame(self.left_scrollable_container,self.file_list)
            self.file_group_frame.grid(row=1,sticky='NESW')
            #print('Created file group frame')
        else:
            self.file_group_frame.file_group_add()

        # make save and continue button
        if((not self.continue_flag) and (not hasattr(self,'continue_button'))):
            self.continue_button = ttk.Button(self.button_container)
            self.continue_button["text"] = "Save and continue"
            self.continue_button["command"] = lambda: [self.timeline.next_step(), self.remove_redaction_cols_page(show_redacted=False)] #adds column selection
            self.continue_button.pack(padx=5,pady=5,side='bottom')

            self.back_button = ttk.Button(self.button_container)
            self.back_button["text"] = "Back"
            self.back_button["command"] = lambda: [self.timeline.prev_step()]
            self.back_button.pack(padx=1,pady=2,side='bottom')

            # added (might want to move elsewhere, bc it can keep duplicating)
            self.show_file_dropdown(self.file_list,False)
        else:
            self.continue_button['state'] = 'normal'

        self.continue_flag = True


    """
    remove file from those which we want to redact
    """
    def remove_file(self,fname):
        self.file_group_frame.handle_file_destruction(fname.get_name())
        fname.destroy_items()

        if(hasattr(self.left_scrollable_container,'file_drop_menu')):
            self.file_drop_menu['values'] = [dfile.get_name() for dfile in self.file_list]

        # also remove from dropdown menu
        print(f'Removing {fname.get_name()}')
        self.options.remove(fname.get_name())
        self.file_drop_menu['values'] = self.options

        # can't redact files if list is empty
        if(not self.file_list):
            self.continue_button['status'] = 'disabled'
            self.continue_flag = False
            self.upload_button["text"] = "Select file(s) to upload"

            self.file_drop_menu.forget()

        # may not want to use del, but unlikely we get nonmatching key
        #del self.file_list[fname]
        self.file_list.remove(fname)


    """
    page for importing files and uploading data
    """
    def select_files_page(self):
        self.upload_button = ttk.Button(self.result_tabs_container)
        self.upload_button["text"] = "Select file(s) to upload"
        self.upload_button["command"] = self.upload_file
        self.upload_button.grid(row=0,column=0)

        #label for status messages
        self.context_label = ttk.Label(self.context_container)
        self.context_label["text"] = ''
        self.context_label.pack(fill='x',padx=5,pady=5,anchor='center',side='top')


    """
    shows the files we can preview
    """
    def show_file_dropdown(self,f_list,show_redacted=True):
        if(f_list):
            self.options = [(n_file.get_name()) for n_file in f_list]
            self.options.insert(0,'(Select a File to Preview)')
        else:
            self.options = ['(Select a File to Preview)']

        # datatype of dropdown menu text
        self.box_value = tk.StringVar()
        self.box_value.set(self.options[0])

        # create dropdown menu
        self.file_drop_menu = ttk.Combobox(self.left_scrollable_container,textvariable=self.box_value,values=self.options,state='readonly')
        self.file_drop_menu.grid(row=0,sticky='NESW')

        if(not show_redacted):
            self.file_drop_menu.bind('<<ComboboxSelected>>',self.show_csv_file_preview)
        else:
            self.file_drop_menu.bind('<<ComboboxSelected>>',self.show_redaction_results_preview)


    """
    page for removing columns to *not* be redacted
    """
    def remove_redaction_cols_page(self,show_redacted=True):
        # remove upload button
        self.upload_button.grid_forget()
        self.continue_flag = False

        # delete buttons/labels for uploaded files
        self.clear_frame(self.result_tabs_container)
        # TODO: add selection functionality,grey out cont button until cols selected?

        self.file_group_frame.hide_matrix() # can still use group structure for viewing files tho
        self.group_info = self.file_group_frame.get_info()
        #print(self.group_info)

        # now we have full group information
        for group in self.group_info:
            #print(group)
            new_group = DataFileGroup(gname=group['file_group_name'],gidx=len(self.group_list),files=group['files'],group_files=group['datafiles'])
            self.group_list.append(new_group)



        self.continue_button["command"] = lambda: [self.timeline.next_step(), self.start_redaction_process()]
        self.back_button["command"] = lambda: [self.timeline.prev_step(), self.select_files_page()]
        self.continue_button["text"] = 'Begin redaction'

        #label for status messages
        self.context_label = ttk.Label(self.context_container)
        self.context_label["text"] = 'Select the columns to ignore during redaction, if any. We will NOT look for identifiable information in these columns.'
        self.context_label.pack(fill='x',padx=5,pady=5,anchor='center',side='top')

        if(not show_redacted):
            self.file_drop_menu.bind('<<ComboboxSelected>>',lambda e: self.show_csv_file_preview(e,col_redaction=True))
        else:
            #self.file_drop_menu.bind('<<ComboboxSelected>>',self.show_redacted_csv_file_preview)
            self.file_drop_menu.bind('<<ComboboxSelected>>',self.show_redaction_results_preview)

        '''
        Triggers when transitioning from import file page to column redaction
        '''
        if hasattr(self, 'preview_table') and not show_redacted: #refreshes the canvas so that it now is highlightable
            fname = f'{self.file_drop_menu.get()}'  # issue is that combobox only displays the filename rn for readability--TODO: fix for entire filepath
            dfile = self.get_dfile_with_fname(fname)  # careful with this!!!! possible collisions
            self.preview_table.bind("<Button-1>",lambda event:self.on_click_header(event,dfile))
            self.preview_table.redraw()



    """
    # we want to redact all columns *not* selected, so start with all cols
    # and then remove the ones we click on (unless re-added)
    """
    def on_click_header(self,event,dfile):
        col_idx = self.preview_table.get_col_clicked(event)  # get string header title???
        clicked_col = self.preview_table.model.columnNames[col_idx]
        if(clicked_col not in dfile.get_cols_to_redact()):
            dfile.settings.add_col_to_redact(clicked_col)
            self.preview_table.allrows = True
            self.preview_table.setcellColor(rows=0,cols=[col_idx],newColor='white',redraw=True,key='bg')  #key='bg' is default
            self.preview_table.allrows = False
        else:
            dfile.settings.remove_col_to_redact(clicked_col)
            self.continue_flag = True
            self.preview_table.allrows = True
            self.preview_table.setcellColor(rows=0,cols=[col_idx],newColor='gray',redraw=True,key='bg')
            self.preview_table.allrows = False

        #print(dfile.get_name(),dfile.cols_to_redact)


    """
    gets file path using file name
    """
    def get_dfile_with_fname(self,fname):
        for item in self.file_list:
            temp = item.get_name()
            if(temp == fname):  # DNI path, so possible duplicate (!)
                return item


    """
    preview a csv file when selected from dropdown
    """
    # is suuuuuper slow for large files, so: pagination
    def show_csv_file_preview(self,cb_event = True,col_redaction=False):  #dfile
        fname = f'{self.file_drop_menu.get()}'  # issue is that combobox only displays the filename rn for readability--TODO: fix for entire filepath
        dfile = self.get_dfile_with_fname(fname)  # careful with this!!!! possible collisions

        if(not dfile):
            return
        fname = dfile.get_path()
        df = dfile.original_df

        if not col_redaction:
            dfile.remove_button.grid(row=0,column=1)

        self.preview_table = TableDisplayCSV(parent=self.preview_scrollable_container,datafile=dfile)
        if col_redaction:
            self.preview_table.bind("<Button-1>",lambda event:self.on_click_header(event,dfile))

        self.preview_table.grid(row=0,column=0,sticky='NESW')
        self.on_frame_config()


    """
    while running redaction, show splash screen that shows we're working on it
    """
    def show_redact_loading_screen(self):
        self.loading_label = ttk.Label(self.context_container,text='Redaction in progress...',anchor='center')
        self.loading_label.pack(fill='both',padx=5,pady=5,anchor='center',side='top')

        ### Add loadig splash page ###

        gif_li = [] ## initiate empty array for gif img storage in sequence

        gif_img = Image.open("gifs/redact_duck.gif") # load target gif img

        ### crrate iterator for target gif and loop and append to gif li

        for img in ImageSequence.Iterator(gif_img):
            img = ImageTk.PhotoImage(img)
            gif_li.append(img)


        ### create top level page to overlay main software page

        top = tk.Toplevel()
        top.geometry("1250x980")
        label = ttk.Label(top)
        label.place(x=0, y=0, anchor='center')
        ttk.Label(top,text="Redacting Your Documents Now...", font= ('Aerial 25')).pack(pady=50)

        num_files = len([f for f in self.file_list]) ### number files to redact in list

        ### while loop to repeat gif until all files are redacted...
        while num_files > 0:
            for img in gif_li:

                label.configure(image=img)
                top.update()
                time.sleep(.25)

                label.pack()

            num_files -= 1


        # Wait for the toplevel window to be closed
        self.loading_label.update_idletasks()

        ### automatically remove loading/splash page
        top.destroy()


    """
    prep app page for redaction, run redaction on each file and display results
    """
    def start_redaction_process(self):
        self.clear_frame(self.preview_scrollable_container)
        self.clear_frame(self.left_scrollable_container)

        # show loading screen while redaction is in progress
        self.show_redact_loading_screen()

        # move on to next step
        for data_file in self.file_list:
            data_file.info_df = pd.DataFrame(columns=INFO_HEADERS)
            self.redact_tokens_in_files(data_file)
            data_file.is_processed = True

        # after process completes, automatically go to redaction_complete page
        self.show_redaction_summary(self.tokenized_data)

    """
    run redaction on a given file
    """
    # ***should not display anything other than loading***
    def redact_tokens_in_files(self,data_file):
        idable_cols = data_file.get_cols_to_redact()

        idable_toks = []
        custom_limit = self.terms_redact_custom.count

        #idable_cols = ['p_utts']  # TODO: delete. this is just for testing so we can click through faster

        for feat_col in idable_cols:
            # idable_toks.tolist() if want series -> list format

            new_token_list,\
            glob_tok_list,\
            new_replaced_utts = run_redaction_full(feat_col,idable_toks,custom_limit,data_file)

            self.tokenized_data += new_token_list
            #self.replacement_data.append(new_replaced_utts)
            self.add_toks_to_category(new_token_list)

            data_file.settings.check_tok_edits_ipa()

            data_file.write_redaction_info(glob_tok_list,INFO_HEADERS)
            data_file.replace_redacted_cols(feat_col,new_replaced_utts)  # NOTE: there is an indexing problem here when iterating over noun chunks

        #print(self.token_buckets)

    # get items with certain category and sort into the proper bucket
    def add_toks_to_category(self,tok_list):
        for txt,prob,tok in tok_list:
            cat = tok._.category
            self.update_dict_with_list_vals(self.token_buckets,cat,tok)

    def update_dict_with_list_vals(self,t_dict,cat,new_val,app_flag=True):  # TODO: global terms instead of instances?  # TODO: add custom categories?
        temp_val = list(t_dict[cat])
        if(app_flag):
            temp_val.append(new_val)
        else:
            temp_val.remove(new_val)
        temp_dict = dict({cat:temp_val})
        t_dict.update(temp_dict)

    # move a token from one category to another
    def move_tok_from_category(self,tok,cat_1,cat_2):
        # remove token from self.token_buckets[cat_1]
        self.update_dict_with_list_vals(self.token_buckets,cat_1,tok,app_flag=False)

        # add to self.token_buckets[cat_2]
        self.update_dict_with_list_vals(self.token_buckets,cat_2,tok)


    """
    display results of redaction.
    """
    def show_redaction_summary(self,redacted=None):
        self.clear_frame(self.preview_scrollable_container)
        if hasattr(self,'loading_label'):
            self.loading_label.forget()

        self.context_label['text'] = 'Redaction complete! Select a file to view redacted tokens.'

        self.continue_button["command"] = lambda: [self.timeline.next_step(), self.export_files_page()]
        self.continue_button["text"] = 'Continue to export'

        self.show_file_dropdown(self.file_list,True)

        self.view_redacted_docs_button = tk.Button(self.result_tabs_container,text='View file with redactions',\
            command=self.show_redacted_file_results)
        self.view_redacted_overview_button = tk.Button(self.result_tabs_container,text='View redaction summary',\
            command=self.show_redacted_terms_results)
        self.tabs_statuses[self.view_redacted_docs_button] = 'off'
        self.tabs_statuses[self.view_redacted_overview_button] = 'off'
        self.view_active_button(self.view_redacted_overview_button)
        self.show_redaction_results_preview()
        #self.view_redacted_overview_button['state'] = 'disabled' # grey out
        self.view_redacted_docs_button.grid(row=0,column=0)
        self.view_redacted_overview_button.grid(row=0,column=1)

        self.potential_terms_button = tk.Button(self.result_tabs_container,text='View NON-redacted summary',\
            command=self.preview_potential_terms)
        self.potential_terms_button.grid(row=0,column=2)
        self.tabs_statuses[self.potential_terms_button] = 'off'

        # ability to change redaction settings
        self.view_redaction_settings_button = tk.Button(self.result_tabs_container,text='Edit redaction categories',\
            command=self.finalize_redaction_categories)
        self.view_redaction_settings_button.grid(row=0,column=3)
        self.tabs_statuses[self.view_redaction_settings_button] = 'off'

        self.custom_terms_settings_button = tk.Button(self.result_tabs_container,text='Add custom terms',\
            command=self.project_settings_add_terms)
        self.custom_terms_settings_button.grid(row=0,column=4)
        self.tabs_statuses[self.custom_terms_settings_button] = 'off'

        self.identifiability_settings_button = tk.Button(self.result_tabs_container,text='Adjust identifiability settings',\
            command=self.project_identifiability_settings)
        self.identifiability_settings_button.grid(row=0,column=5)
        self.tabs_statuses[self.identifiability_settings_button] = 'off'


    """
    show redacted file preview
    """
    def show_redacted_file_results(self):
        self.show_redactions = True
        self.view_active_button(self.view_redacted_docs_button)

        self.show_redaction_results_preview()


    """
    show information on redacted terms
    """
    def show_redacted_terms_results(self):
        self.show_redactions = False
        self.view_active_button(self.view_redacted_overview_button)

        self.show_redaction_results_preview()


    """
    see which tab we're on in the results page
    """
    def view_active_button(self,button):
        for butt in self.tabs_statuses:
            if(self.tabs_statuses[butt] == 'on'):
                self.tabs_statuses[butt] = 'off'
                butt['state'] = 'normal'
                butt.configure(bg="#333333")

        self.tabs_statuses[button] = 'on'
        button['state'] = 'disabled'
        button.configure(fg="#ffffff")
        button.configure(bg="#007fff")

    """
    handles review page
    > redacted file preview:
    - shows file with redactions
    - shows redacted terms (strikeout) replaced with new term (bold, maroon)
    > redacted terms review:
    - shows terms caught by our system
    - allows user to globally ignore a term
    - see stats for each term
    """
    # NOTE (s)
    # default show all rows up to page limit at a time
    # could access with pre-established sql queries (instead of typing in rows with this item, have a dropbox)

    # TODO: also make option to only show redacted columns and hovertext for column headers?
    def show_redaction_results_preview(self,cb_event=True):  # TODO: check file extension for proper display (eg text file may be differently structured than csv)
        self.clear_frame(self.preview_scrollable_container)
        fname = f'{self.file_drop_menu.get()}'

        # could add attribute to dfile with either a redacted csv or a sqlite table or similar
        dfile = self.get_dfile_with_fname(fname)
        if(not dfile):
            return

        if(self.show_redactions):
            show_info = False
            dfile.redacted_df.fillna('')
            df = dfile.redacted_df
            #print(df.to_string())
            self.context_label['text'] = 'This is a preview of your file with the settings applied. To change a setting for a file, click on a tab above the preview.\nTo export your files, press the save and continue button.'
        else:
            show_info = True
            df = dfile.info_df
            #print(df.to_string())
            tok_count = str(df.shape[0])
            self.context_label['text'] = 'This page contains information about the individual terms that have been redacted by our system.\nUnique terms initially flagged: ' + tok_count + '\nTotal terms initially flagged: '

        if('show' in df.columns):
            #df = df.drop(df['show'] == 0)
            df = df[df.show == 1]
            df = df.drop(columns=['show'])
        self.preview_results_table = TableDisplayCSV(parent=self.preview_scrollable_container,datafile=dfile,show_redacted=self.show_redactions,show_info=show_info)
        self.preview_results_table.grid(row=0,column=0,sticky='NESW')
        self.on_frame_config()


    """
    handles the page of the application that views potentially identifiable terms that have NOT been redacted
    """
    def preview_potential_terms(self,start=0):
        self.clear_frame(self.preview_scrollable_container)
        self.view_active_button(self.potential_terms_button)

        self.context_label['text'] = 'We have found these terms to be POTENTIALLY identifiable, but they have NOT been redacted.'
        self.context_label['text'] += '\nThese are terms that may be either very close to the identifiability threshold, similar phonetically to identifiable terms, or possible misspellings or mistranscriptions.'

        fname = f'{self.file_drop_menu.get()}'

        # could add attribute to dfile with either a redacted csv or a sqlite table or similar
        dfile = self.get_dfile_with_fname(fname)
        if(not dfile):
            return

        idx = 0
        items = list(dfile.settings.non_idable_compendium.keys())
        end = min(len(items),start+VIEW_ROW_LIMIT)
        #end = len(items)

        phon_str = 'Phonetic similarity to:'
        edit_str = 'Edit-distance similarity to:'
        thresh_str = 'Identifiability probability (current threshold: XX)'

        col_widget = tk.Text(self.preview_scrollable_container,height=1,width=20)
        col_widget.grid(row=idx,column=0,sticky='NESW')
        col_widget.insert(tk.END,'Term')

        edit_widget = tk.Text(self.preview_scrollable_container,height=2,width=30)
        edit_widget.grid(row=idx,column=1,sticky='NESW')
        edit_widget.insert(tk.END,edit_str)

        phon_widget = tk.Text(self.preview_scrollable_container,height=2,width=30)
        phon_widget.grid(row=idx,column=2,sticky='NESW')
        phon_widget.insert(tk.END,phon_str)

        thresh_widget = tk.Text(self.preview_scrollable_container,height=2,width=30)
        thresh_widget.grid(row=idx,column=3,sticky='NESW')
        thresh_widget.insert(tk.END,thresh_str)

        # refresh scrollable area
        self.on_frame_config()

        idx += 1

        for item in items:#[start:end]:
            if(idx-1 < start):
                continue
            if(idx-1 == end):
                break

            similar_terms = dfile.settings.non_idable_compendium[item].keys()

            if(similar_terms):
                phon_str = ''
                edit_str = ''
                thresh_str = ''

                col_widget = tk.Text(self.preview_scrollable_container,height=1,width=20)
                col_widget.grid(row=idx,column=0,sticky='NESW')
                col_widget.insert(tk.END,item)

                edit_widget = tk.Text(self.preview_scrollable_container,height=2,width=30)
                edit_widget.grid(row=idx,column=1,sticky='NESW')
                edit_widget.insert(tk.END,edit_str)

                phon_widget = tk.Text(self.preview_scrollable_container,height=2,width=30)
                phon_widget.grid(row=idx,column=2,sticky='NESW')
                phon_widget.insert(tk.END,phon_str)

                thresh_widget = tk.Text(self.preview_scrollable_container,height=2,width=30)
                thresh_widget.grid(row=idx,column=3,sticky='NESW')
                thresh_widget.insert(tk.END,thresh_str)

                for j,ikey in enumerate(similar_terms):
                    #print('\t',ikey,dfile.settings.non_idable_compendium[item][ikey])
                    # item_widget = tk.Text(self.preview_container,height=2,width=30)
                    # item_widget.grid(row=idx,column=j+1)
                    if(dfile.settings.non_idable_compendium[item][ikey]['edits']):
                        #edit_str = ikey + '\n'
                        edit_widget.insert(tk.END,ikey)
                        edit_widget.insert(tk.END,'\n')
                    if(dfile.settings.non_idable_compendium[item][ikey]['phon']):
                        phon_widget.insert(tk.END,ikey)
                        phon_widget.insert(tk.END,'\n')
                    # item_widget.insert(tk.END,item_str)
                    flags = dfile.settings.non_idable_compendium[item][ikey]
                    # item_widget.insert(tk.END,str(flags))
                    #print('\t',item_str)

                # refresh scrollable area
                self.on_frame_config()
                idx += 1


    """
    handles the "add terms" page of the application
    """
    def project_settings_add_terms(self):
        self.clear_frame(self.preview_scrollable_container)
        self.view_active_button(self.custom_terms_settings_button)

        self.file_drop_menu.forget()

        # time.sleep(2)

        self.context_label['text'] = 'Let us know what we should watch out for.'
        self.context_label['text'] += '\nThese are terms that you know should be redacted. We will add these to the identifiable terms we identify and redact.'

        self.display_terms_frame = TermDisplayFrame(self.preview_scrollable_container,
            list_of_files = [x['file_group_name'] for x in self.group_info],
            files = self.file_list,
            file_group_info = self.group_info
        )
        #self.display_terms_frame.pack(side='right')
        self.display_terms_frame.grid(row=2,sticky='NESW')

        # refresh scrollable area
        self.on_frame_config()


    """
    handles the "remove terms" page of the app
    # DEPRECATED
    """
    def project_settings_remove_terms(self):
        self.clear_frame(self.preview_scrollable_container)

        project_settings_add_terms_info = self.display_terms_frame.return_info()
        #print(project_settings_add_terms_info)
        self.display_terms_frame.forget()

        self.context_label['text'] = 'Let us know what we should watch out for.'
        self.context_label['text'] += '\nThese are terms that should NOT be redacted. However, we will still categorize these as identifiable terms when applicable.'

        # update entry button to add terms to ignorelist instead
        # self.add_redacts_button['text'] = 'Add new ignored term'
        # self.add_redacts_button["command"] = lambda list_t=self.terms_to_ignore:self.add_term_to_redaction_list(self.terms_to_ignore)

        self.display_terms_frame = TermDisplayFrame(self.preview_scrollable_container,
            list_of_files=  [x['file_group_name'] for x in self.group_info],
            files = self.file_list,
            file_group_info = self.group_info,
            ignore=True
        )
        #self.display_terms_frame.pack(side='right')
        self.display_terms_frame.grid(row=2,sticky='NESW')

        # refresh scrollable area
        self.on_frame_config()


    """
    Finalize some redaction settings
    """
    def finalize_redaction_categories(self):
        self.view_active_button(self.view_redaction_settings_button)
        self.clear_frame(self.preview_scrollable_container)

        self.context_label['text'] = 'Choose which categories to redact (default is all).'
        self.context_label['text'] += '\nIf you uncheck a category, the tokens (words or word clusters) belonging to that category will no longer be redacted.'

        self.settings_frame = ttk.Frame(self.preview_scrollable_container)
        self.settings_frame.grid(row=0,column=0,sticky='NESW')

        # display categories that we will look for (name, location, etc)
        for curr_row,cat in enumerate(REDACTION_CATEGORIES):
            ck = ttk.Checkbutton(self.settings_frame,variable=None,onvalue=1)
            ck.grid(row=curr_row,column=0)
            ck.focus_set()
            ck.invoke()
            ck.bind("<Button-1>",self.modify_redaction_categories)
            self.new_context_label = ttk.Label(self.settings_frame,text=cat)
            self.new_context_label.grid(row=curr_row,column=1)

        # TODO: group functionality, category descriptions/examples

        # TODO: allow user to rank importance of the categories
        self.rankings_frame = ttk.Frame(self.preview_scrollable_container)
        self.rankings_frame.grid(row=0,column=1,sticky='NESW')

        # refresh scrollable area
        self.on_frame_config()


    def modify_show_category_terms(self,cat,dfile):
        dfile.info_df.loc[dfile.info_df['Token Category'] == cat,'show'] = 0


    def modify_redaction_categories(self,event):
        cat_row = event.widget.grid_info()['row']

        cat = self.redaction_categories_dict[cat_row]
        try:
            self.redaction_categories.remove(cat)
            self.modify_show_category_terms(cat)
        except:
            # make sure it adds back in right spot!!
            i = cat_row
            cat_preceding = self.redaction_categories_dict[i]
            while (i > 0) and (cat_preceding not in self.redaction_categories): #can be optimized ?
                i -= 1
                cat_preceding = self.redaction_categories_dict[i]
            if (i == 0) and (cat_preceding not in self.redaction_categories):
                self.redaction_categories.insert(0, cat)
            else:
                idx = self.redaction_categories.index(cat_preceding) + 1
                self.redaction_categories.insert(idx, cat)


    def project_identifiability_settings(self):
        self.clear_frame(self.preview_scrollable_container)
        self.view_active_button(self.identifiability_settings_button)

        self.context_label['text'] = 'Our automated classifiers predict a probability that each token (word or word cluster) in the transcript should be redacted.'
        self.context_label['text'] += '\nHere, you may set the probability threshold above which tokens will be redacted and below which they will not be redacted. Aim to set the slider so that as many of the redaction decisions as possible are correct.'
        self.context_label['text'] += '\nYou may change redaction settings for individual tokens in the XX tab.'

        # frame to hold information about the slider and terms
        self.slider_frame = ttk.Frame(self.preview_scrollable_container)
        self.slider_frame.grid(row=0,column=0,sticky='NESW')

        self.threshold_slider_descript = ttk.Label(self.slider_frame,text='Current threshold: 0.5')
        self.threshold_slider_descript.grid(row=0,column=1,columnspan=2)
        self.threshold_slider = ttk.Scale(self.slider_frame,orient='horizontal',\
                                          command=self.update_threshold_slider,\
                                          variable=self.redaction_threshold,\
                                          from_=0.1,to=0.99)
        self.threshold_slider.grid(row=1,column=1,columnspan=2)

        # terms that WILL be redacted
        self.terms_redacted_frame = tk.Frame(self.slider_frame)
        self.terms_redacted_frame.grid(row=3,column=0,sticky='NESW')

        terms_text_0 = 'Sample terms being redacted\n(very high predicted probability)'
        self.terms_redacted_descript = WrapperLabel(self.terms_redacted_frame,text=terms_text_0,anchor='center')
        self.terms_redacted_descript.pack(fill='x',side='top',padx=5,pady=5)

        # terms that WILL be redacted, but near threshold
        self.terms_above_thresh_frame = tk.Frame(self.slider_frame)#,background='green')
        self.terms_above_thresh_frame.grid(row=3,column=1,sticky='NESW')

        terms_text_1 = 'Sample terms being redacted\n(just above the probability threshold)'
        self.terms_above_thresh_descript = WrapperLabel(self.terms_above_thresh_frame,text=terms_text_1,anchor='center')
        self.terms_above_thresh_descript['background'] = 'green'
        self.terms_above_thresh_descript.pack(fill='x',side='top',padx=5,pady=5)

        # terms that WILL NOT be redacted, but near threshold
        self.terms_below_thresh_frame = tk.Frame(self.slider_frame)#,background='orange')
        self.terms_below_thresh_frame.grid(row=3,column=2,sticky='NESW')

        terms_text_2 = 'Sample terms NOT being redacted\n(just below the probability threshold)'
        self.terms_below_thresh_descript = WrapperLabel(self.terms_below_thresh_frame,text=terms_text_2,anchor='center')
        self.terms_below_thresh_descript['background'] = 'orange'
        self.terms_below_thresh_descript.pack(fill='x',side='top',padx=5,pady=5)

        # terms that WILL NOT be redacted
        self.terms_not_redacted_frame = tk.Frame(self.slider_frame)
        self.terms_not_redacted_frame.grid(row=3,column=3,sticky='NESW')

        terms_text_3 = 'Sample terms NOT being redacted\n(very low predicted probability)'
        self.terms_not_redacted_descript = WrapperLabel(self.terms_not_redacted_frame,text=terms_text_3,anchor='center')
        self.terms_not_redacted_descript.pack(fill='x',side='top',padx=5,pady=5)

        # create term labels
        terms_0 = ''
        terms_1 = ''
        terms_2 = ''
        terms_3 = ''
        self.terms_redacted = WrapperLabel(self.terms_redacted_frame,text=terms_0,anchor='center')
        self.terms_redacted.pack(fill='x',side='bottom',padx=5,pady=5)

        self.terms_above_thresh = WrapperLabel(self.terms_above_thresh_frame,text=terms_1,anchor='center')
        #self.terms_above_thresh['background'] = 'green'
        self.terms_above_thresh.pack(fill='x',side='bottom',padx=5,pady=5)

        self.terms_below_thresh = WrapperLabel(self.terms_below_thresh_frame,text=terms_2,anchor='center')
        #self.terms_below_thresh['background'] = 'orange'
        self.terms_below_thresh.pack(fill='x',side='bottom',padx=5,pady=5)

        self.terms_not_redacted = WrapperLabel(self.terms_not_redacted_frame,text=terms_3,anchor='center')
        self.terms_not_redacted.pack(fill='x',side='bottom',padx=5,pady=5)

    def get_slider_val(self):
        return 'Current threshold: {: .2f}'.format(self.redaction_threshold.get())

    def int_of_float(self,num):
        return num * pow(10,PROB_ROUNDING)

    def get_threshold_idx(self,lst):
        curr_thresh = self.redaction_threshold.get()
        thresh_idx = (np.abs(lst - curr_thresh)).argmin()  # check that the term is also above/below
        thresh_int = self.int_of_float(curr_thresh)
        try:
            while(self.int_of_float(lst[thresh_idx]) < thresh_int):  # if we need equality of floats, np.isclose(num1,num2)
                thresh_idx -= 1
        except:
            thresh_idx = -1

        if thresh_idx < 0:
            return len(lst) // 2

        return thresh_idx

    def update_threshold_slider(self,event):
        self.threshold_slider_descript.configure(text=self.get_slider_val())


        token_list = list(self.tokenized_data)
        token_list = np.asarray(token_list)
        token_list = token_list[token_list[:, 1].argsort()]
        # to see all tokens
        # for i in token_list:
        #     print(i)
        # print(token_list)

        # update the example tokens here with their probs
        lst = np.asarray(self.tokenized_data)[:,1]
        thresh_idx = self.get_threshold_idx(lst)

        terms_0 = ''
        terms_1 = ''
        terms_2 = ''
        terms_3 = ''
        for i in range(VIEW_TERM_LIMIT):
            terms_0 += str(token_list[i][0]) +'\n'  #+ f' ({token_list[i][1]})' + '\n'
            terms_1 = str(token_list[thresh_idx-(VIEW_TERM_LIMIT-i)][0]) +'\n'  + terms_1 # + f' ({token_list[thresh_idx-(i+1)][1]})' + '\n' + terms_1  # reverse order
            terms_2 += str(token_list[thresh_idx+i][0]) +'\n'  # + f' ({token_list[thresh_idx+i][1]})' + '\n'
            terms_3 = str(token_list[-(VIEW_TERM_LIMIT-i)][0]) +'\n'  +terms_3 # + f' ({token_list[-(i+1)][1]})' + '\n' + terms_3  # reverse order

        self.terms_redacted['text'] = terms_0
        self.terms_above_thresh['text'] = terms_1
        self.terms_below_thresh['text'] = terms_2
        self.terms_not_redacted['text'] = terms_3


    """
    handle file export page
    """
    def export_files_page(self):
        self.clear_frame(self.preview_scrollable_container)
        self.clear_frame(self.result_tabs_container)
        # self.clear_frame(self.left_scrollable_container)

        self.files_no_folder = list(self.file_list)

        self.continue_button["command"] = lambda: [self.timeline.next_step(), self.final_export_check()]
        self.continue_button["text"] = 'Export ALL files'

        self.back_button["command"] = lambda: [self.timeline.prev_step(), self.show_redaction_summary()]

        self.export_button = ttk.Button(self.result_tabs_container)
        self.export_button["text"] = "Add directory"
        self.export_button["command"] = self.add_export_dir
        self.export_button.grid(row=0,column=0)

        self.context_label["text"] = 'Please select a file directory (folder) in which to save redacted files. You may then select which redacted files to put in each directory.'

        self.show_dir_dropdown(self.export_dir_list)

        #f = fd.asksaveasfile(initialfile='Untitled.txt',defaultextension='.csv',filetypes=[('CSV Files', '.csv'),('Text Files', '.txt')])


    def add_export_dir(self,event=None):
        export_dir = fd.askdirectory()

        if(export_dir == ''):
            return

        idx = 0
        existing_file_flag = False
        end_fname = export_dir.split('/')[-1]
        for curr_file in self.export_dir_list:
            if(end_fname == curr_file):
                existing_file_flag = True
                break
        if(not existing_file_flag):
            self.export_dir_list.append(export_dir)

        # update dropdown menu also
        if(hasattr(self,'dir_drop_menu')):
            self.dir_drop_menu['values'] = [fname for fname in self.export_dir_list]
            self.options = [export_dir.split('/')[-1] for export_dir in self.export_dir_list]
            self.options.insert(0,'(Select a Directory)')

    # dropdown for choosing export directory
    def show_dir_dropdown(self,dir_list):
        if(dir_list):
            self.options = list(dir_list)
            self.options.insert(0,'(Select a Directory)')
        else:
            self.options = ['(Select a Directory)']

        # datatype of dropdown menu text
        self.box_value = tk.StringVar()
        self.box_value.set(self.options[0])

        # create dropdown menu
        self.dir_drop_menu = ttk.Combobox(self.result_tabs_container,textvariable=self.box_value,values=self.options,state='readonly')
        self.dir_drop_menu.grid(row=0,column=1,sticky='NESW')

        self.drop_label = ttk.Label(self.result_tabs_container,text='Select a directory to preview which files will be exported to it.')
        self.drop_label.grid(row=0,column=2,sticky='NESW')

        self.dir_drop_menu.bind('<<ComboboxSelected>>',self.display_contained_files)


    def display_contained_files(self,cb_event=True):
        export_dir = f'{self.dir_drop_menu.get()}'

        for i,group in enumerate(self.group_list):
            group_name = 'Group ' + str(i)  + ': ' + group.group_name
            group.display_frame = ttk.Frame(self.preview_scrollable_container)
            group.display_frame.grid(row=0,column=i,sticky='NESW')

            group.chk_button = ttk.Checkbutton(group.display_frame,text=group_name,variable=tk.IntVar())
            group.chk_button.bind('<Button-1>',
                lambda e: group.export_checkbox_group(
                    e,export_dir
                )
            )
            group.chk_button.grid(row=0,column=0,sticky='NSW')
            for j,dfile in enumerate(group.group_files):
                if type(dfile) is type(None):
                    continue
                #dfile = group.get_dfile_with_fname(fname)
                dfile.chk_button = ttk.Checkbutton(group.display_frame,text=dfile.get_name(),variable=tk.IntVar())
                dfile.chk_button.bind('<Button-1>',
                    lambda e: dfile.export_checkbox_file(
                        e,export_dir
                    )
                )
                dfile.chk_button.grid(row=j+1,column=0,sticky='NSW')


    def final_export_check(self):
        # check that each file has an export directory
        if(not self.files_no_folder == []):
            # TODO: display message about which file is missing a diriectory
            print(self.files_no_folder)
            return

        self.exit_page()


    def export_file(self,dfile):
        try:
            # save redacted dfile to its chosen export directory
            # if file exists in directory already, skip and flag
            fname = dfile.get_name().split('.')[0] + '_REDACTED' + dfile.extension
            fpath = dfile.settings.export_directory + '/' + fname
            # TODO: check for duplicates, different file types
            # write dfile.redacted_df to fpath
            dfile.redacted_df.to_csv(fpath,encoding='utf-8')

            fname = dfile.get_name().split('.')[0] + '_INFO' + dfile.extension
            fpath = dfile.settings.export_directory + '/' + fname
            print(fpath)
            dfile.info_df.to_csv(fpath,encoding='utf-8')
        except Exception as e:
            print('ERRRRRRRRRR:',e)


    """
    last page of app! export and everything else has been finalized
    """
    def exit_page(self):
        for dfile in self.file_list:
            self.export_file(dfile)
        self.clear_frame(self.preview_scrollable_container)
        self.clear_frame(self.result_tabs_container)
        self.clear_frame(self.left_scrollable_container)

        self.context_label["text"] = 'Export complete! Thank you :)'


"""
to run in terminal (may need python3 instead based on your env settings):
$ python app.py
"""
def main():
    #start app
    app = RedactingTool(tk.Tk())

    app.mainloop()

if __name__ == "__main__":
    main()