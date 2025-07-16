from project_x_py.project_x import ProjectX

project_x = ProjectX(username="jeffw102", api_key="Q1yl6AVP0aWGigl176fLN5O7gooUaJGTaSLUtKQMoZE=")

data = project_x.get_data(
    instrument="MGC",
    days=1,
    interval=15,
    unit=1,
)

print(data)