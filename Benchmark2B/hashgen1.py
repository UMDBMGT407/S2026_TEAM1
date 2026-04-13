from werkzeug.security import generate_password_hash

print("Manager hash:")
print(generate_password_hash("manager123"))

print("\nShiftLead hash:")
print(generate_password_hash("shift123"))

print("\nEmployee hash:")
print(generate_password_hash("employee123"))
