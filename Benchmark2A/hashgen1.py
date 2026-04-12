from werkzeug.security import generate_password_hash

print("Manager hash:")
print(generate_password_hash("manager123"))

print("\nShiftLead hash:")
print(generate_password_hash("shift123"))

print("\nEmployee hash:")
print(generate_password_hash("employee123"))

# NEW
# Generate hash for the default password assigned to all new users
# The add_user() route in app.py assigns "default123" automatically.
print("\nDefault (new user) hash:")
print(generate_password_hash("default123"))
