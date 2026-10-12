# SecJ_Weak_Cryptographic_Hash_Hardcoded_Salt

- **规则ID**：071d9ca2-da83-44bc-8429-f1977a3f3313
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

采用硬编码处理 salt 绝非一个好方法。这不仅是因为所有项目开发人员都可以使用 hardcoded salt 来查看该 salt，而且还会使解决这一问题变得极其困难。一旦将该代码投入生产，则无法轻易更改该 salt。如果攻击者知道该 salt 的值，他们就可以计算出该应用程序的“彩虹表”，并更轻松地确定散列值。

**【正确示例】**

```
public void testCalculatePasswordHashGood(String username, char[] password) {
    SecureRandom random = SecureRandom.getInstance("SHA1PRNG");
    byte[] salt = new byte[8];
    random.nextBytes(salt);
    Util.calculatePasswordHash(username, password, salt);
}

```
**【错误示例】**

```
public void testCalculatePasswordHashBad(String username, char[] password) {
    /* POTENTIAL FLAW: Hardcoded Salt。*/
    Util.calculatePasswordHash(username, password, "salt".getBytes());
}

```
**【修复建议】**

salt 始终不能为硬编码
