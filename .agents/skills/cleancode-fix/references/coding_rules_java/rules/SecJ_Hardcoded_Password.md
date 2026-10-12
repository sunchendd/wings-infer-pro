# SecJ_Hardcoded_Password

- **规则ID**：5379ec8b-7f85-4b69-8fcb-4ad7142b4c3d
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

当密码以明文形式存储在应用程序的属性文件或其他配置文件中时，会发生 password management 漏洞。

**【正确示例】**

```
public void test01Bad() {
    SecureRandom random = SecureRandom.getInstance("SHA1PRNG");
    byte[] pwd = new byte[8];
    random.nextBytes(pwd);
}

```
**【错误示例】**

```
public void test01Bad() {
    /* POTENTIAL FLAW: Hardcoded passwords may compromise system security in a way that cannot be easily remedied */
    String pwd = "abcdef";
}

```
**【修复建议】**

不能采用明文的形式存储密码。
