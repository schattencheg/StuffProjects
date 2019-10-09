import requests

url = 'https://yandex.ru/images/search?text=raven%20dc&isize=wallpaper&wp=wh16x9_1920x1080'
r = requests.get(url)
with open('local.html', 'w') as output_file:
  #output_file.write(r.text.encode('cp1251'))
  output_file.write(r.text)


