# G.NOD.04 解压文件必须进行安全检查

- **规则ID**：22336f59-d952-436a-8e92-ac02fb894300
- **更新时间**：2025-06-05 04:35:00

---

**【问题级别】**

一般

**【描述】**

攻击者有可能上传一个很小的zip文件，但是完全解压缩之后达到几百万GB甚至更多，消耗完磁盘空间导致系统或程序无法正常运行。因此在解压缩文件时需要限制所使用的磁盘空间。



因此，在解压前最少进行以下几点基础安全检查：

1.文件个数是否超出业务预期个数；

2.文件大小是否超出业务预期大小。

**【正确示例】**

```
const fs = require('fs');
const pathmodule = require('path');
const JSZip = require('jszip');
const MAX_FILES = 10000;
const MAX_SIZE = 1000000000; // 1 GB
let fileCount = 0;
let totalSize = 0;
let targetDirectory = __dirname + '/archive_tmp';
fs.readFile("foo.zip", function(err, data) {
  if (err) throw err;
  JSZip.loadAsync(data).then(function (zip) {
    zip.forEach(function (relativePath, zipEntry) {
      fileCount++;
      if (fileCount > MAX_FILES) {
        throw 'Reached max. number of files';
      }
      // Prevent ZipSlip path traversal (S6096)
      const resolvedPath = pathmodule.join(targetDirectory, zipEntry.name);
      if (!resolvedPath.startsWith(targetDirectory)) {
        throw 'Path traversal detected';
      }
      if (!zip.file(zipEntry.name)) {
        fs.mkdirSync(resolvedPath);
      } else {
        zip.file(zipEntry.name).async('nodebuffer').then(function (content) {
          totalSize += content.length;
          if (totalSize > MAX_SIZE) {
            throw 'Reached max. size';
          }
          fs.writeFileSync(resolvedPath, content);
        });
      }
    });
  });
});

```
**【错误示例】**

```
const fs = require('fs');
const pathmodule = require('path');
const JSZip = require('jszip');
const MAX_FILES = 10000;
const MAX_SIZE = 1000000000; // 1 GB
let fileCount = 0;
let totalSize = 0;
let targetDirectory = __dirname + '/archive_tmp';
fs.readFile("foo.zip", function(err, data) {
  if (err) throw err;
  JSZip.loadAsync(data).then(function (zip) {
    zip.forEach(function (relativePath, zipEntry) {
      // Prevent ZipSlip path traversal (S6096)
      const resolvedPath = pathmodule.join(targetDirectory, zipEntry.name);
      if (!resolvedPath.startsWith(targetDirectory)) {
        throw 'Path traversal detected';
      }
      if (!zip.file(zipEntry.name)) {
        fs.mkdirSync(resolvedPath);
      } else {
        zip.file(zipEntry.name).async('nodebuffer').then(function (content) {
          totalSize += content.length;
          if (totalSize > MAX_SIZE) {
            throw 'Reached max. size';
          }
          fs.writeFileSync(resolvedPath, content);
        });
      }
    });
  });
});

```
**【修复建议】**

解压文件必须进行安全检查
