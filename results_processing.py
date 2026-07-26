# results verification
from database import DatabaseManager

# count votes for each presidential candidate
def president_vote_count():
    try:
        with DatabaseManager() as db:
            # Query to select all president IDs from the presidents table
            select_presidents_sql = "SELECT ID FROM presidents"
            db.execute_query(select_presidents_sql)
            presidents = db.fetch_all()
            
            # Query to count the total number of votes cast
            count_total_votes_sql = "SELECT COUNT(*) FROM voterinfo WHERE voted = '1'"
            db.execute_query(count_total_votes_sql)
            total_votes_count = db.fetch_one()[0]

            # Loop through each president
            for president in presidents:
                president_id = president[0]

                # Query to count votes for the current president
                count_votes_sql = "SELECT COUNT(*) FROM voterinfo WHERE president_vote = %s"
                db.execute_query(count_votes_sql, (president_id,))
                votes_count = db.fetch_one()[0]

                # Update the number of votes for the current president
                update_votes_sql = "UPDATE presidents SET number_of_votes = %s WHERE ID = %s"
                db.execute_query(update_votes_sql, (votes_count, president_id))

                # Calculate the vote percentage for the current president
                vote_percentage = round((votes_count / total_votes_count) * 100, 1) if total_votes_count > 0 else 0

                # Update the vote percentage for the current president
                update_percentage_sql = "UPDATE presidents SET vote_percentage = %s WHERE ID = %s"
                db.execute_query(update_percentage_sql, (f"{vote_percentage}%", president_id))

    except Exception as e:
        print(f"An error occurred in president_vote_count: {e}")


def create_table_if_not_exists(table_name):
    # WARNING: Creating tables dynamically based on user input/data is generally bad design.
    # Maintaining logic for compatibility.
    try:
        with DatabaseManager() as db:
            # Fetching the names of MP candidates from 'members_of_parliament' table
            fetch_table = 'members_of_parliament'
            query = f"SELECT * FROM {fetch_table} WHERE constituency = %s"
            db.execute_query(query, (table_name,))
            result = db.fetch_one()

            if result is None:
                print(f"No data found for constituency '{table_name}'.")
                return

            container = []
            
            # Collect the result into a container
            # Result is a tuple. 
            # Logic from original code: iterate from index 2 to end?
            for row in result:
                container.append(row)

            result_length = len(result)

            # Check if the table already exists
            db.execute_query(f"SHOW TABLES LIKE '{table_name}'")
            exists = db.fetch_one()

            if not exists:  # if table does not exist
                # Sanitize table name (basic)
                safe_table_name = "".join(x for x in table_name if x.isalnum() or x == '_')
                
                table_schema = "id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255), number_of_votes INT"
                db.execute_query(f"CREATE TABLE {safe_table_name} ({table_schema})")

                # Insert data into the new table
                for index in range(2, result_length):
                    data_to_insert = container[index]
                    insert_name_into_table(safe_table_name, data_to_insert)
            else:
                # Insert data into the existing table
                for index in range(2, result_length):
                    data_to_insert = container[index]
                    insert_name_into_table(table_name, data_to_insert, check_exists=True)

    except Exception as e:
        print(f"An error occurred in create_table_if_not_exists: {e}")


def insert_name_into_table(table_name, data, check_exists=False):
    if data is None:
        return
        
    try:
        with DatabaseManager() as db:
            column_name = 'name'
            if check_exists:
                check_query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {column_name} = %s)"
                db.execute_query(check_query, (data,))
                exists = db.fetch_one()[0]
                if exists:
                    return

            insert_query = f"INSERT INTO {table_name} ({column_name}) VALUES (%s)"
            db.execute_query(insert_query, (data,))
            if not check_exists:
                 # Only print on new bulk insert? Matches original somewhat.
                 pass
            print(f"Data {data} inserted successfully into {table_name}.")
            
    except Exception as err:
        print(f"Error inserting name: {err}")


def insert_vcounts_into_table(constituency_table, mp_id):
    fetch_table = 'voterinfo'
    try:
        with DatabaseManager() as db:
            # Prepare the SQL query to select all records from the specified row
            # mp_vote in voterinfo maps to WHAT? The name? or ID?
            # In voting.py: `sql = "UPDATE voterinfo SET mp_vote = %s WHERE voter_id = %s"`
            # voter_choice_mp is the NAME input by user.
            
            # Logic here: `WHERE mp_vote = %s`.
            # But the MP table (constituency table created dynamically) stores 'name' and 'id'.
            # function arg is `mp_id`.
            # So we need to get the NAME associated with that mp_id from the constituency table FIRST?
            # Or is mp_vote storing the ID? The code says `voter_choice_mp = input("Cast vote (Enter Name) ->> ")`
            # So mp_vote stores NAME.
            
            # But `insert_vcounts_into_table` is called with `row_3[0]` which is `id` from `constituency_table`.
            # We need the NAME corresponding to that ID to count votes.
            
            # Get Name for this ID
            name_query = f"SELECT name FROM {constituency_table} WHERE id = %s"
            db.execute_query(name_query, (mp_id,))
            name_res = db.fetch_one()
            
            if name_res:
                mp_name = name_res[0]
                query = f"SELECT count(*) FROM {fetch_table} WHERE constituency = %s and mp_vote = %s"
                db.execute_query(query, (constituency_table, mp_name,))
                result = db.fetch_one()
    
                if result:
                    query = f"UPDATE {constituency_table} SET number_of_votes = %s WHERE id = %s"
                    db.execute_query(query, (result[0], mp_id))
            
    except Exception as err:
        print(f"Error counting votes: {err}")


def mp_vote_count():
    try:
        with DatabaseManager() as db:
            query = "SELECT constituency FROM members_of_parliament"
            db.execute_query(query)
            results = db.fetch_all()

            for row in results:
                table = row[0]
                create_table_if_not_exists(table)

                query_1 = f"SELECT id FROM {table}"
                db.execute_query(query_1)
                result_1 = db.fetch_all()

                for row_3 in result_1:
                    insert_vcounts_into_table(table, row_3[0])

    except Exception as err:
        print(f"Error in mp_vote_count: {err}")


def display_results():
    try:
        print(f'\n-Presidential vote results ')
        with DatabaseManager() as db:
            # fetch presidential results from database
            pres_query = "SELECT * FROM presidents"
            db.execute_query(pres_query)
            pres_results = db.fetch_all()
            for LIST in pres_results:
                # LIST: id, party, name, votes, percentage
                print(f'{LIST[0]} | {LIST[1]} - {LIST[2]} | {LIST[3]} | - {LIST[4]}')

            # Calculate and store
            president_vote_count()
            
            # Recalculate MP votes
            mp_vote_count()
            
            # Display MP results?
            # Original code used global `table` which was set in `mp_vote_count` loop (so it was only the LAST table).
            # This logic seems flawed in original: it only printed results for the LAST constituency processed.
            # I will improve it to print ALL.
            
            query = "SELECT constituency FROM members_of_parliament"
            db.execute_query(query)
            constituencies = db.fetch_all()
            
            for const_row in constituencies:
                table = const_row[0]
                print(f'\n-MP vote results for {table} constituency')
                mp_query = f"SELECT * FROM {table}"
                db.execute_query(mp_query)
                mp_results = db.fetch_all()
                for LIST in mp_results:
                     # id, name, votes
                    print(f'{LIST[0]} | {LIST[1]} - | {LIST[2]} |')

    except Exception as err:
        print(f"Error displaying results: {err}")
