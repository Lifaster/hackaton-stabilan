import pandas as pd
import matplotlib.pyplot as plt


#async def handle_file(message: types.Message):

#file = await bot.get_file(message.document.file_id)
#path = file.file_path
#downloaded = await bot.download_file(path)

#with open("стабилан.xlsx", "wb") as f:
    #f.write(downloaded.read())

df = pd.read_excel("стабилан.xlsx")
xls = pd.ExcelFile("стабилан.xlsx")
data = {}

data["romberg"] = pd.read_excel(xls, "Допусковый контроль")
data["open"] = pd.read_excel(xls, "Ог")
data["closed"] = pd.read_excel(xls, "зг")
data["target_signal"] = pd.read_excel(xls, "Мишень стаб.сигнал")
data["target"] = pd.read_excel(xls, "Мишень")

# print(type(df))
# print(df.head())
# print(df.shape)
# print(df.describe())
# print(df.values)
# # график

print(data)
plt.figure()

x = df["MO(x),мм"]
y = df["MO(y),мм"]

plt.figure()

plt.plot(x, y)

plt.xlabel("X (mm)")
plt.ylabel("Y (mm)")

plt.title("Center of Pressure trajectory")

plt.savefig("graph1.png")

plt.close()

plt.bar(df["Допусковый_контроль"], df["KoefRomb,%"])

plt.xticks(rotation=45)
plt.ylabel("KoefRomb")

plt.savefig("graph.png")

    #await message.answer_photo(open("graph.png","rb"))
