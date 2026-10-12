# G.WSQ.01 禁止在 Web SQL database和Indexed database数据库中存储敏感数据

- **规则ID**：caa532d6-d845-477c-95f1-e58dcdac128c
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

致命

**【描述】**

Web SQL database和Indexed database存储的数据是明文的，客户端上有本地访问权限的操作系统用户都能访问，容易泄露。而且，利用XSS漏洞，攻击者可以构造脚本对Web SQL database和Indexed database数据库进行操纵，数据容易被窃取，即使对敏感数据加密，一旦密钥泄露，也将导致敏感数据泄露。因此，禁止在WebSQL database和Indexed database数据库中存储敏感数据。

**【正确示例】**

```
let db=openDatabase("testDB","1.0.0","d1",1024*1024);
db.transaction(function (tx) {
    tx.executeSql('INSERT INTO province (id, name) VALUES (1, "zhejiang")');
}

```
**【错误示例】**

```
let db=openDatabase("testDB","1.0.0","d1",1024*1024);
db.transaction(function (tx) {
    tx.executeSql('INSERT INTO account (id, password) VALUES (1, "password")');
}

```
**【修复建议】**

禁止在 Web SQL database和Indexed database数据库中存储敏感数据
