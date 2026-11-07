# Usar PyMySQL como implementación de MySQLdb para evitar depender de mysqlclient
# (requiere libmysqlclient y herramientas de compilación en el contenedor).
# El backend django.db.backends.mysql importa "MySQLdb", que ahora apuntará a PyMySQL.
import pymysql

pymysql.install_as_MySQLdb()
