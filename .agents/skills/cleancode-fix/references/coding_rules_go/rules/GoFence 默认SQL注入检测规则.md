# GoFence 默认SQL注入检测规则

- **规则ID**：ba275f00-00e9-425c-9904-df997971c90d
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

SQL注入是指使用外部数据构造的SQL语句所代表的数据库操作与预期不符，过执行恶意SQL语句，进而将任意SQL代码插入数据库查询，这样可能会导致信息泄露或者数据被篡改。SQL注入产生的根本原因是使用外部数据直接拼接SQL语句改。

**【正确示例】**

```
```
func TestEntryPoint0(sqlPara string) {	
	//外部信息进行检测
	if IsValidSqlParam(sqlPara) {
	 	sqlStr1 := "select * from Test where playname='" + sqlPara + "'"
		sqlQuery(sqlStr1) //ok, valid param, condition verification is not supported.
	 }
}

func sqlQuery(sqlStr string, args ...interface{}) {
	driver := "mysql"
	dataSourceName := "root:root@tcp(localhost:3306)/demo?charset=utf8"
	db, err := sql.Open(driver, dataSourceName)
	if err != nil {
		fmt.Println("Connect DB error.")
		return
	}
	defer db.Close()
	rows, _ := db.Query(sqlStr, args)
	fmt.Println(rows)
}
func IsValidSqlParam(param string) bool {
	if param == "test" {
		return true
	}
	return false
}
```

```
**【错误示例】**

```
```
func TestEntryPoint0(sqlPara string) {
	sqlStr0 := "select * from Test where playname='" + sqlPara + "'"
	 sqlQuery(sqlStr0) //error, Assembles SQL statements based on external input, SQL injection may occur.
}

func sqlQuery(sqlStr string, args ...interface{}) {
	driver := "mysql"
	dataSourceName := "root:root@tcp(localhost:3306)/demo?charset=utf8"
	db, err := sql.Open(driver, dataSourceName)
	if err != nil {
		fmt.Println("Connect DB error.")
		return
	}
	defer db.Close()
	rows, _ := db.Query(sqlStr, args)
	fmt.Println(rows)
}
```

```
**【修复建议】**

防止SQL注入的方式主要可以分为两类：

使用预处理参数化查询 ，避免以字符串为拼接方式查询

对不可信数据进行校验

---------参考华为go语言安全编程规范2.1
