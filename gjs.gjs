#!/usr/bin/gjs
imports.gi.versions.Gtk = '3.0' // Adjust this if you're using GTK 4
const { Gtk, Gdk, Gio, GLib, GObject } = imports.gi;
const Gda = imports.gi.Gda;

// SQLite file
const DB_FILE = '/home/niklas/scripts/projects/sheet-music2/file_index.db';

// Search algorithms
const SearchAlgorithm = {
  CONTAINS: 'Contains',
  STARTS_WITH: 'Starts with'
};

// Function to run an SQLite query and return results using GDA
function run_query(db_file, query, params) {
  let result = [];

  // Open the SQLite connection
  let provider = Gda.Connection.open_from_string('SQLite', `DB_NAME=${db_file}`, null, Gda.ConnectionOptions.READ_ONLY);

  if (!provider) {
      throw new Error("Failed to open SQLite connection");
  }

  // Prepare the SQL query using Gda.SqlParser
  let parser = new Gda.SqlParser();
  let stmt = parser.parse_string(query)[0];  // Parse the query into a statement

  // Create a Gda.Set for parameters and bind them to the query
  let param_set = new Gda.Set();

  for (let i = 0; i < params.length; i++) {
      // Create a new holder with a valid GType and directly set the string value
      let holder = new Gda.Holder({ g_type: GObject.TYPE_STRING });
      holder.set_value(params[i]); // Directly bind the string value
      param_set.add_holder(holder);
  }

  // Execute the query and fetch results
  let data_model = provider.statement_execute_select(stmt, param_set);

  if (data_model) {
      let row_count = data_model.get_n_rows();
      for (let i = 0; i < row_count; i++) {
          // Use data_model.get_value_at() to extract the value at the correct column
          let g_value = data_model.get_value_at(0, i);  // Get the GValue at column 0, row i
          
          // Check the type of the returned value and extract the string
          if (g_value instanceof GObject.Value) {
              let string_value = g_value.get_string();  // Correct method for extracting a string
              result.push(string_value);
          }
      }
  }

  provider.close();

  return result;
}





// Main GUI Application
class FileSearchApp {
  constructor() {
    this.app = new Gtk.Application();
    this.app.connect('activate', this.onActivate.bind(this));
  }

  // Handler for application activation
  onActivate() {
    this.window = new Gtk.ApplicationWindow({
      application: this.app,
      title: 'File Search',
      default_height: 400,
      default_width: 600
    });

    this.search_algorithm = SearchAlgorithm.CONTAINS;

    let vbox = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });

    // Search bar
    this.search_entry = new Gtk.Entry({ placeholder_text: 'Search files...' });
    this.search_entry.connect('changed', () => this.onSearchChanged());

    vbox.pack_start(this.search_entry, false, false, 0);

    // Dropdown to choose the search algorithm
    let combo_box = new Gtk.ComboBoxText();
    combo_box.append_text(SearchAlgorithm.CONTAINS);
    combo_box.append_text(SearchAlgorithm.STARTS_WITH);
    combo_box.set_active(0); // Default: Contains
    combo_box.connect('changed', () => {
      this.search_algorithm = combo_box.get_active_text();
      this.onSearchChanged(); // Re-search using the new algorithm
    });
    vbox.pack_start(combo_box, false, false, 0);

    // List to display search results
    this.list_store = new Gtk.ListStore();
    this.list_store.set_column_types([GObject.TYPE_STRING]);

    this.list_view = new Gtk.TreeView({ model: this.list_store });
    let renderer = new Gtk.CellRendererText();
    let column = new Gtk.TreeViewColumn({ title: 'Filename' });
    column.pack_start(renderer, true);
    column.add_attribute(renderer, 'text', 0); // Attach the cell renderer to the first column (index 0)
    this.list_view.append_column(column);

    let scrolled_window = new Gtk.ScrolledWindow();
    scrolled_window.add(this.list_view);
    vbox.pack_start(scrolled_window, true, true, 0);

    this.window.add(vbox);
    this.window.show_all();

    // ADD THIS BLOCK: Test query to fetch all records in the file_index table
    let test_query = 'SELECT name FROM file_index'; // Query to get all records
    let all_records = run_query(DB_FILE, test_query, []); // No parameters
    console.log("All records in file_index table:", all_records); // Log all records
  }

  // Handler for when the search field changes
  onSearchChanged() {
    let search_term = this.search_entry.get_text().trim();
    console.log("Search term:", search_term); // Log the search term

    if (search_term.length === 0) {
      this.update_list_view([]);
      return;
    }

    // Define the query based on the selected search algorithm
    let query;
    let search_param = search_term;
    if (this.search_algorithm === SearchAlgorithm.CONTAINS) {
      query = 'SELECT name FROM file_index WHERE name LIKE ?';
      search_param = `%${search_term}%`;
    } else if (this.search_algorithm === SearchAlgorithm.STARTS_WITH) {
      query = 'SELECT name FROM file_index WHERE name LIKE ?';
      search_param = `${search_term}%`;
    }

    console.log("Executing query:", query, "with param:", search_param); // Log the query and parameter

    // Execute the query and update the list view
    let results = run_query(DB_FILE, query, [search_param]);

    console.log("Query results:", results); // Log the results

    this.update_list_view(results);
  }

  // Update the list view with new results
  update_list_view(results) {
    console.log("Updating list view with results:", results); // Log the update

    this.list_store.clear();  // Clear the existing list

    for (let result of results) {
      let iter = this.list_store.append();  // Append a new row
      this.list_store.set(iter, [0], [result]);  // Set the result into the row
      console.log("Added to list:", result);  // Log each added item
    }
  }
}

// Start the application
let app = new FileSearchApp();
app.app.run([]);
