import tkinter as tk
from tkinter import ttk


class Select2Tkinter(ttk.Frame):
    """
        A class for creating a custom select widget for tkinter.

        Attributes
        ----------
        parent :
            The parent widget.
        list_of_values : list
            The list of values to be displayed in the dropdown.
        width : int
            The width of the widget.
        height : int
            The height of the widget.
        select_mode : str
            The selection mode of the widget.
        search_entry_font : tuple
            The font of the search entry.
        search_entry_bg : str
            The background color of the search entry.
        search_entry_fg : str
            The foreground color of the search entry.
        search_entry_border_color : str
            The border color of the search entry.
        search_entry_border_width : int
            The border width of the search entry.
        dropdown_list_font : tuple
            The font of the dropdown list.
        dropdown_list_bg : str
            The background color of the dropdown list.
        dropdown_list_fg : str
            The foreground color of the dropdown list.
        dropdown_list_border_color : str
            The border color of the dropdown list.
        dropdown_list_border_width : int
            The border width of the dropdown list.
        dropdown_list_highlight_bg : str
            The highlight background color of the dropdown list.
        dropdown_list_highlight_fg : str
            The highlight foreground color of the dropdown list.
        
        Methods
        -------
        get_value()
            Returns the selected value(s).
        update_list_of_values(list_of_values)
            Updates the list of values in the dropdown.
        clear()
            Clears the selected value(s).
    """

    def __init__(self, parent, list_of_values: list = None, width: int = 200, height: int = 200,
                 select_mode: str = "single", **kwargs):
        super().__init__(parent)
        if list_of_values is None:
            list_of_values = []
        self.parent = parent
        self.width = width
        self.height = height
        self.list_of_values = list_of_values
        self.select_mode = select_mode

        # Get the custom configuration for the widget
        self.search_entry_font = kwargs.get("search_entry_font", ("Arial", 10))
        self.search_entry_bg = kwargs.get("search_entry_bg", "white")
        self.search_entry_fg = kwargs.get("search_entry_fg", "black")
        self.search_entry_border_color = kwargs.get("search_entry_border_color", "#B0B0B0")
        self.search_entry_border_width = kwargs.get("search_entry_border_width", 1)

        self.dropdown_list_font = kwargs.get("dropdown_list_font", ("Arial", 10))
        self.dropdown_list_bg = kwargs.get("dropdown_list_bg", "white")
        self.dropdown_list_fg = kwargs.get("dropdown_list_fg", "black")
        self.dropdown_list_border_color = kwargs.get("dropdown_list_border_color", "#B0B0B0")
        self.dropdown_list_border_width = kwargs.get("dropdown_list_border_width", 1)
        self.dropdown_list_highlight_bg = kwargs.get("dropdown_list_highlight_bg", "#D3D3D3")
        self.dropdown_list_highlight_fg = kwargs.get("dropdown_list_highlight_fg", "black")

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_list)

        self.search_entry = tk.Entry(self, textvariable=self.search_var, width=self.width,
                                     font=self.search_entry_font,
                                     bg=self.search_entry_bg, fg=self.search_entry_fg,
                                     highlightcolor=self.search_entry_border_color,
                                     highlightbackground=self.search_entry_border_color,
                                     highlightthickness=self.search_entry_border_width,
                                     bd=0)
        self.search_entry.grid(row=0, column=0, sticky="ew")

        self.listbox_frame = tk.Frame(self)
        self.listbox_frame.grid(row=1, column=0, sticky="ew")

        self.listbox = tk.Listbox(self.listbox_frame, width=self.width, height=self.height,
                                  selectmode=self.select_mode,
                                  font=self.dropdown_list_font,
                                  bg=self.dropdown_list_bg, fg=self.dropdown_list_fg,
                                  highlightcolor=self.dropdown_list_border_color,
                                  highlightbackground=self.dropdown_list_border_color,
                                  highlightthickness=self.dropdown_list_border_width,
                                  selectbackground=self.dropdown_list_highlight_bg,
                                  selectforeground=self.dropdown_list_highlight_fg,
                                  bd=0,
                                  exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(self.listbox_frame, orient="vertical", command=self.listbox.yview)
        self.scrollbar.pack(side="right", fill="y")

        self.listbox.config(yscrollcommand=self.scrollbar.set)

        self.update_list()

        self.search_entry.bind("<FocusIn>", self.show_list)
        self.search_entry.bind("<FocusOut>", self.hide_list)
        self.listbox.bind("<FocusIn>", self.show_list)
        self.listbox.bind("<FocusOut>", self.hide_list)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        self.listbox_frame.grid_remove()

        self.selected_values = []

    def update_list(self, *args):
        """
            Updates the list of values in the dropdown based on the search query.
        """
        search_term = self.search_var.get().lower()
        self.listbox.delete(0, "end")
        for value in self.list_of_values:
            if isinstance(value, tuple):
                if search_term in str(value[1]).lower():
                    self.listbox.insert("end", value)
            else:
                if search_term in str(value).lower():
                    self.listbox.insert("end", value)

    def show_list(self, event=None):
        """
            Shows the dropdown list.
        """
        self.listbox_frame.grid()

    def hide_list(self, event=None):
        """
            Hides the dropdown list.
        """
        if self.focus_get() != self.search_entry and self.focus_get() != self.listbox:
            self.listbox_frame.grid_remove()

    def on_select(self, event=None):
        """
            Handles the selection of a value from the dropdown list.
        """
        if self.select_mode == "single":
            self.selected_values = self.listbox.get(self.listbox.curselection())
            self.search_var.set(self.selected_values[1] if isinstance(self.selected_values, tuple)
                                else self.selected_values)
            self.listbox_frame.grid_remove()
        elif self.select_mode == "multiple":
            self.selected_values = [self.listbox.get(i) for i in self.listbox.curselection()]
            self.search_var.set(", ".join([str(v[1]) if isinstance(v, tuple) else str(v) for v in self.selected_values]))

    def get_value(self):
        """
            Returns the selected value(s).
        """
        return self.selected_values

    def update_list_of_values(self, list_of_values: list):
        """
            Updates the list of values in the dropdown.
        """
        self.list_of_values = list_of_values
        self.update_list()

    def clear(self):
        """
            Clears the selected value(s).
        """
        self.selected_values = []
        self.search_var.set("")
        self.listbox.selection_clear(0, "end")


if __name__ == '__main__':
    """
        Example usage of the Select2Tkinter class.
    """
    root = tk.Tk()
    root.title("Select2Tkinter Example")
    root.geometry("500x500")

    # Example 1: Single selection
    list_of_values = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
    select2 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="single")
    select2.pack(pady=10)

    def get_value():
        print(select2.get_value())

    button = tk.Button(root, text="Get Value", command=get_value)
    button.pack(pady=10)

    # Example 2: Multiple selection
    list_of_values = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
    select3 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="multiple")
    select3.pack(pady=10)

    def get_value2():
        print(select3.get_value())

    button2 = tk.Button(root, text="Get Value", command=get_value2)
    button2.pack(pady=10)

    # Example 3: Single selection with tuple
    list_of_values = [(1, "apple"), (2, "banana"), (3, "cherry"), (4, "date"), (5, "elderberry"), (6, "fig"),
                      (7, "grape")]
    select4 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="single")
    select4.pack(pady=10)

    def get_value3():
        print(select4.get_value())

    button3 = tk.Button(root, text="Get Value", command=get_value3)
    button3.pack(pady=10)

    # Example 4: Multiple selection with tuple
    list_of_values = [(1, "apple"), (2, "banana"), (3, "cherry"), (4, "date"), (5, "elderberry"), (6, "fig"),
                      (7, "grape")]
    select5 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="multiple")
    select5.pack(pady=10)

    def get_value4():
        print(select5.get_value())

    button4 = tk.Button(root, text="Get Value", command=get_value4)
    button4.pack(pady=10)

    # Example 5: Custom configuration
    list_of_values = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
    select6 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="single",
                             search_entry_font=("Times New Roman", 12),
                             search_entry_bg="lightblue",
                             search_entry_fg="black",
                             search_entry_border_color="blue",
                             search_entry_border_width=2,
                             dropdown_list_font=("Times New Roman", 12),
                             dropdown_list_bg="lightblue",
                             dropdown_list_fg="black",
                             dropdown_list_border_color="blue",
                             dropdown_list_border_width=2,
                             dropdown_list_highlight_bg="blue",
                             dropdown_list_highlight_fg="white")
    select6.pack(pady=10)

    def get_value5():
        print(select6.get_value())

    button5 = tk.Button(root, text="Get Value", command=get_value5)
    button5.pack(pady=10)

    # Example 6: Update list of values
    list_of_values = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
    select7 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="single")
    select7.pack(pady=10)

    def get_value6():
        print(select7.get_value())

    button6 = tk.Button(root, text="Get Value", command=get_value6)
    button6.pack(pady=10)

    def update_list():
        new_list = ["one", "two", "three", "four", "five", "six", "seven"]
        select7.update_list_of_values(new_list)

    button7 = tk.Button(root, text="Update List", command=update_list)
    button7.pack(pady=10)

    # Example 7: Clear selection
    list_of_values = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
    select8 = Select2Tkinter(root, list_of_values, width=200, height=100, select_mode="multiple")
    select8.pack(pady=10)

    def get_value7():
        print(select8.get_value())

    button8 = tk.Button(root, text="Get Value", command=get_value7)
    button8.pack(pady=10)

    def clear_selection():
        select8.clear()

    button9 = tk.Button(root, text="Clear Selection", command=clear_selection)
    button9.pack(pady=10)

    # Example 8: No values
    select9 = Select2Tkinter(root, width=200, height=100, select_mode="single")
    select9.pack(pady=10)

    def get_value8():
        print(select9.get_value())

    button10 = tk.Button(root, text="Get Value", command=get_value8)
    button10.pack(pady=10)

    # Example 9: No values and update
    select10 = Select2Tkinter(root, width=200, height=100, select_mode="single")
    select10.pack(pady=10)

    def get_value9():
        print(select10.get_value())

    button11 = tk.Button(root, text="Get Value", command=get_value9)
    button11.pack(pady=10)

    def update_list2():
        new_list = ["one", "two", "three", "four", "five", "six", "seven"]
        select10.update_list_of_values(new_list)

    button12 = tk.Button(root, text="Update List", command=update_list2)
    button12.pack(pady=10)

    root.mainloop()