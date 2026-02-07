(function () {
  const mountNode = document.getElementById("asset-overview-root");
  if (!mountNode) {
    return;
  }

  const config = JSON.parse(mountNode.dataset.config || "{}");
  const csrfToken = mountNode.dataset.csrf || "";
  const element = React.createElement;

  function normalizeAssetRow(item) {
    return {
      id: item.id,
      name: item.name,
      ownerId: item.owner ? String(item.owner.id) : "",
      status: item.status || "ACTIVE",
      groupIds: item.groups ? item.groups.map(function (group) { return String(group.id); }) : [],
      osFamilyId: item.os_family ? String(item.os_family.id) : "",
      osVersionId: item.os_version ? String(item.os_version.id) : "",
      ports: item.ports || [],
      unassignedInterfaces: item.unassigned_interfaces || [],
    };
  }

  function normalizeInterfaceRow(item) {
    const activeIp = item.active_ip || null;
    return {
      id: item.id,
      assetId: item.asset_id,
      assetName: item.asset_name,
      portId: item.port ? String(item.port) : "",
      identifier: item.identifier || "",
      macAddress: item.mac_address || "",
      notes: item.notes || "",
      active: !!item.active,
      networkId: activeIp && activeIp.network ? String(activeIp.network.id) : "",
      ipAddress: activeIp ? activeIp.address || "" : "",
      ipStatus: activeIp ? activeIp.status || "STATIC" : "STATIC",
      hostname: activeIp ? activeIp.hostname || "" : "",
      hadActiveIp: !!activeIp,
      ipHistory: item.ip_history || [],
    };
  }

  function cloneAssetRowsById(rows) {
    return rows.reduce(function (acc, row) {
      acc[row.id] = Object.assign({}, row, { groupIds: row.groupIds.slice() });
      return acc;
    }, {});
  }

  function cloneInterfaceRowsById(rows) {
    return rows.reduce(function (acc, row) {
      acc[row.id] = Object.assign({}, row, {
        ipHistory: row.ipHistory.slice(),
      });
      return acc;
    }, {});
  }

  function flattenErrors(input, prefix, result) {
    if (result === undefined) {
      result = [];
    }
    if (prefix === undefined) {
      prefix = "";
    }
    if (input === null || input === undefined) {
      return result;
    }
    if (Array.isArray(input)) {
      input.forEach(function (item) {
        flattenErrors(item, prefix, result);
      });
      return result;
    }
    if (typeof input === "object") {
      Object.keys(input).forEach(function (key) {
        const nextPrefix = prefix ? prefix + "." + key : key;
        flattenErrors(input[key], nextPrefix, result);
      });
      return result;
    }
    result.push(prefix ? prefix + ": " + String(input) : String(input));
    return result;
  }

  function OverviewApp() {
    const [activeView, setActiveView] = React.useState("asset");

    const [assetRows, setAssetRows] = React.useState([]);
    const [savedAssetRows, setSavedAssetRows] = React.useState({});
    const [assetErrors, setAssetErrors] = React.useState({});
    const [savingAssetIds, setSavingAssetIds] = React.useState([]);
    const [expandedAssets, setExpandedAssets] = React.useState({});

    const [interfaceRows, setInterfaceRows] = React.useState([]);
    const [savedInterfaceRows, setSavedInterfaceRows] = React.useState({});
    const [interfaceErrors, setInterfaceErrors] = React.useState({});
    const [savingInterfaceIds, setSavingInterfaceIds] = React.useState([]);

    const [lookups, setLookups] = React.useState({
      users: [],
      groups: [],
      osFamilies: [],
      osVersions: [],
      networks: [],
      ports: [],
    });

    const [bulkTextAsset, setBulkTextAsset] = React.useState("");
    const [bulkInfoAsset, setBulkInfoAsset] = React.useState("");
    const [bulkTextInterface, setBulkTextInterface] = React.useState("");
    const [bulkInfoInterface, setBulkInfoInterface] = React.useState("");
    const [globalError, setGlobalError] = React.useState("");

    const versionsByFamily = React.useMemo(function () {
      return lookups.osVersions.reduce(function (acc, version) {
        const key = String(version.family_id);
        if (!acc[key]) {
          acc[key] = [];
        }
        acc[key].push(version);
        return acc;
      }, {});
    }, [lookups.osVersions]);

    const portsByAsset = React.useMemo(function () {
      return lookups.ports.reduce(function (acc, port) {
        const key = String(port.asset_id);
        if (!acc[key]) {
          acc[key] = [];
        }
        acc[key].push(port);
        return acc;
      }, {});
    }, [lookups.ports]);

    const loadAssets = React.useCallback(function () {
      return fetch(config.apiBaseUrl + "/assets/?type=COMPUTER", {
        credentials: "same-origin",
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("load assets failed");
          }
          return response.json();
        })
        .then(function (data) {
          const normalized = data.map(normalizeAssetRow);
          setAssetRows(normalized);
          setSavedAssetRows(cloneAssetRowsById(normalized));
        });
    }, []);

    const loadInterfaces = React.useCallback(function () {
      return fetch(config.apiBaseUrl + "/interfaces/?q=", {
        credentials: "same-origin",
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("load interfaces failed");
          }
          return response.json();
        })
        .then(function (data) {
          const normalized = data.map(normalizeInterfaceRow);
          setInterfaceRows(normalized);
          setSavedInterfaceRows(cloneInterfaceRowsById(normalized));
        });
    }, []);

    const loadLookups = React.useCallback(function () {
      return Promise.all([
        fetch(config.apiBaseUrl + "/users/?q=", { credentials: "same-origin" }).then(function (response) {
          return response.json();
        }),
        fetch(config.apiBaseUrl + "/groups/?q=", { credentials: "same-origin" }).then(function (response) {
          return response.json();
        }),
        fetch(config.apiBaseUrl + "/os-families/?q=", { credentials: "same-origin" }).then(function (response) {
          return response.json();
        }),
        fetch(config.apiBaseUrl + "/os-versions/?q=", { credentials: "same-origin" }).then(function (response) {
          return response.json();
        }),
        fetch(config.apiBaseUrl + "/networks/?q=", { credentials: "same-origin" }).then(function (response) {
          return response.json();
        }),
        fetch(config.apiBaseUrl + "/ports/?q=", { credentials: "same-origin" }).then(function (response) {
          return response.json();
        }),
      ]).then(function (results) {
        setLookups({
          users: results[0] || [],
          groups: results[1] || [],
          osFamilies: results[2] || [],
          osVersions: results[3] || [],
          networks: results[4] || [],
          ports: results[5] || [],
        });
      });
    }, []);

    const reloadAll = React.useCallback(function () {
      return Promise.all([loadAssets(), loadInterfaces(), loadLookups()]);
    }, [loadAssets, loadInterfaces, loadLookups]);

    React.useEffect(function () {
      reloadAll().catch(function () {
        setGlobalError("Failed to load overview data.");
      });
    }, [reloadAll]);

    function setAssetValue(rowId, key, value) {
      setAssetRows(function (currentRows) {
        return currentRows.map(function (row) {
          if (row.id !== rowId) {
            return row;
          }
          return Object.assign({}, row, { [key]: value });
        });
      });
      setAssetErrors(function (current) {
        const next = Object.assign({}, current);
        delete next[rowId];
        return next;
      });
    }

    function setAssetGroupValues(rowId, selectedValues) {
      setAssetRows(function (currentRows) {
        return currentRows.map(function (row) {
          if (row.id !== rowId) {
            return row;
          }
          return Object.assign({}, row, { groupIds: selectedValues });
        });
      });
      setAssetErrors(function (current) {
        const next = Object.assign({}, current);
        delete next[rowId];
        return next;
      });
    }

    function setInterfaceValue(rowId, key, value) {
      setInterfaceRows(function (currentRows) {
        return currentRows.map(function (row) {
          if (row.id !== rowId) {
            return row;
          }
          return Object.assign({}, row, { [key]: value });
        });
      });
      setInterfaceErrors(function (current) {
        const next = Object.assign({}, current);
        delete next[rowId];
        return next;
      });
    }

    function revertAssetRow(rowId) {
      const saved = savedAssetRows[rowId];
      if (!saved) {
        return;
      }
      setAssetRows(function (currentRows) {
        return currentRows.map(function (row) {
          if (row.id !== rowId) {
            return row;
          }
          return Object.assign({}, saved, { groupIds: saved.groupIds.slice() });
        });
      });
      setAssetErrors(function (current) {
        const next = Object.assign({}, current);
        delete next[rowId];
        return next;
      });
    }

    function revertInterfaceRow(rowId) {
      const saved = savedInterfaceRows[rowId];
      if (!saved) {
        return;
      }
      setInterfaceRows(function (currentRows) {
        return currentRows.map(function (row) {
          if (row.id !== rowId) {
            return row;
          }
          return Object.assign({}, saved, { ipHistory: saved.ipHistory.slice() });
        });
      });
      setInterfaceErrors(function (current) {
        const next = Object.assign({}, current);
        delete next[rowId];
        return next;
      });
    }

    function handleAssetCellKeyDown(event, rowId) {
      if (event.key === "Enter") {
        event.preventDefault();
        saveAssetRow(rowId);
      } else if (event.key === "Escape") {
        event.preventDefault();
        revertAssetRow(rowId);
      }
    }

    function handleInterfaceCellKeyDown(event, rowId) {
      if (event.key === "Enter") {
        event.preventDefault();
        saveInterfaceRow(rowId);
      } else if (event.key === "Escape") {
        event.preventDefault();
        revertInterfaceRow(rowId);
      }
    }

    function saveAssetRow(rowId) {
      if (!config.canEdit) {
        return;
      }

      const row = assetRows.find(function (item) {
        return item.id === rowId;
      });
      if (!row) {
        return;
      }

      setSavingAssetIds(function (current) {
        return current.concat(rowId);
      });

      const payload = {
        owner: row.ownerId ? Number(row.ownerId) : null,
        status: row.status,
        groups: row.groupIds.map(function (id) {
          return Number(id);
        }),
        os_family: row.osFamilyId ? Number(row.osFamilyId) : null,
        os_version: row.osVersionId ? Number(row.osVersionId) : null,
      };

      fetch(config.apiBaseUrl + "/assets/" + rowId + "/", {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
      })
        .then(function (response) {
          if (!response.ok) {
            return response.json().then(function (errorData) {
              throw errorData;
            });
          }
          return response.json();
        })
        .then(function () {
          return Promise.all([loadAssets(), loadLookups()]).then(function () {
            setAssetErrors(function (current) {
              const next = Object.assign({}, current);
              delete next[rowId];
              return next;
            });
          });
        })
        .catch(function (errorData) {
          const lines = flattenErrors(errorData);
          setAssetErrors(function (current) {
            return Object.assign({}, current, {
              [rowId]: lines.join(" | ") || "Save failed.",
            });
          });
        })
        .finally(function () {
          setSavingAssetIds(function (current) {
            return current.filter(function (id) {
              return id !== rowId;
            });
          });
        });
    }

    function saveInterfaceRow(rowId) {
      if (!config.canEdit) {
        return;
      }

      const row = interfaceRows.find(function (item) {
        return item.id === rowId;
      });
      if (!row) {
        return;
      }

      if (row.ipAddress && !row.networkId) {
        setInterfaceErrors(function (current) {
          return Object.assign({}, current, {
            [rowId]: "network: Select network when IP is set.",
          });
        });
        return;
      }

      setSavingInterfaceIds(function (current) {
        return current.concat(rowId);
      });

      const payload = {
        identifier: row.identifier,
        mac_address: row.macAddress || null,
        notes: row.notes || "",
        active: row.active,
        port: row.portId ? Number(row.portId) : null,
      };

      if (row.networkId && row.ipAddress) {
        payload.network = Number(row.networkId);
        payload.address = row.ipAddress;
        payload.ip_status = row.ipStatus || "STATIC";
        payload.hostname = row.hostname || "";
      } else if (row.networkId && !row.ipAddress) {
        payload.network = Number(row.networkId);
        payload.clear_ip = true;
      } else if (!row.networkId && !row.ipAddress && row.hadActiveIp) {
        payload.clear_ip = true;
      }

      fetch(config.apiBaseUrl + "/interfaces/" + rowId + "/", {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
      })
        .then(function (response) {
          if (!response.ok) {
            return response.json().then(function (errorData) {
              throw errorData;
            });
          }
          return response.json();
        })
        .then(function () {
          return Promise.all([loadInterfaces(), loadAssets(), loadLookups()]).then(function () {
            setInterfaceErrors(function (current) {
              const next = Object.assign({}, current);
              delete next[rowId];
              return next;
            });
          });
        })
        .catch(function (errorData) {
          const lines = flattenErrors(errorData);
          setInterfaceErrors(function (current) {
            return Object.assign({}, current, {
              [rowId]: lines.join(" | ") || "Save failed.",
            });
          });
        })
        .finally(function () {
          setSavingInterfaceIds(function (current) {
            return current.filter(function (id) {
              return id !== rowId;
            });
          });
        });
    }

    function parseAssetBulkRows(text) {
      return text
        .split("\n")
        .map(function (line) {
          return line.trim();
        })
        .filter(Boolean)
        .map(function (line) {
          const values = line.split("\t");
          const row = { id: Number(values[0]) };

          if (values[1]) {
            row.owner = Number(values[1]);
          }
          if (values[2]) {
            row.status = values[2];
          }
          if (values[3]) {
            row.os_family = Number(values[3]);
          }
          if (values[4]) {
            row.os_version = Number(values[4]);
          }
          if (values[5]) {
            row.groups = values[5]
              .split(",")
              .map(function (part) { return part.trim(); })
              .filter(Boolean)
              .map(function (part) { return Number(part); });
          }

          return row;
        });
    }

    function parseInterfaceBulkRows(text) {
      return text
        .split("\n")
        .map(function (line) {
          return line.trim();
        })
        .filter(Boolean)
        .map(function (line) {
          const values = line.split("\t");
          const row = { id: Number(values[0]) };

          if (values[1]) {
            row.port = Number(values[1]);
          }
          if (values[2]) {
            row.mac_address = values[2];
          }
          if (values[3]) {
            row.network = Number(values[3]);
          }
          if (values[4]) {
            row.address = values[4];
          }
          if (values[5]) {
            row.ip_status = values[5];
          }
          if (values[6]) {
            row.hostname = values[6];
          }
          return row;
        });
    }

    function submitAssetBulkPaste() {
      if (!config.canEdit) {
        return;
      }
      setBulkInfoAsset("");
      setGlobalError("");
      let rowsPayload = [];
      try {
        rowsPayload = parseAssetBulkRows(bulkTextAsset);
      } catch (_error) {
        setBulkInfoAsset("Bulk parse error.");
        return;
      }

      if (rowsPayload.length === 0) {
        setBulkInfoAsset("No rows to import.");
        return;
      }

      fetch(config.apiBaseUrl + "/assets/bulk_update/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ rows: rowsPayload }),
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { status: response.status, data: data };
          });
        })
        .then(function (result) {
          const failed = (result.data.results || []).filter(function (item) {
            return !item.success;
          });
          if (failed.length > 0) {
            setBulkInfoAsset("Bulk finished with " + failed.length + " row errors.");
          } else {
            setBulkInfoAsset("Bulk update successful.");
          }
          return Promise.all([loadAssets(), loadLookups()]);
        })
        .catch(function () {
          setBulkInfoAsset("Bulk update failed.");
        });
    }

    function submitInterfaceBulkPaste() {
      if (!config.canEdit) {
        return;
      }
      setBulkInfoInterface("");
      setGlobalError("");
      let rowsPayload = [];
      try {
        rowsPayload = parseInterfaceBulkRows(bulkTextInterface);
      } catch (_error) {
        setBulkInfoInterface("Bulk parse error.");
        return;
      }

      if (rowsPayload.length === 0) {
        setBulkInfoInterface("No rows to import.");
        return;
      }

      fetch(config.apiBaseUrl + "/interfaces/bulk_update/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ rows: rowsPayload }),
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { status: response.status, data: data };
          });
        })
        .then(function (result) {
          const failed = (result.data.results || []).filter(function (item) {
            return !item.success;
          });
          if (failed.length > 0) {
            setBulkInfoInterface("Bulk finished with " + failed.length + " row errors.");
          } else {
            setBulkInfoInterface("Bulk update successful.");
          }
          return Promise.all([loadInterfaces(), loadAssets(), loadLookups()]);
        })
        .catch(function () {
          setBulkInfoInterface("Bulk update failed.");
        });
    }

    function renderSelectOptions(items, valueKey, labelFn) {
      return items.map(function (item) {
        return element(
          "option",
          {
            key: String(item[valueKey]),
            value: String(item[valueKey]),
          },
          labelFn(item)
        );
      });
    }

    function cellClass(hasError) {
      return "rounded border px-2 py-1 " + (hasError ? "border-red-400 bg-red-50" : "border-slate-300");
    }

    function toggleExpandedAsset(assetId) {
      setExpandedAssets(function (current) {
        const next = Object.assign({}, current);
        next[assetId] = !current[assetId];
        return next;
      });
    }

    function renderNetworkHierarchy(assetRow) {
      const rows = [];

      assetRow.ports.forEach(function (port) {
        rows.push(
          element(
            "tr",
            { key: "port-" + port.id },
            element("td", { className: "px-2 py-1 font-semibold text-slate-800" }, "Port"),
            element("td", { className: "px-2 py-1 font-semibold" }, port.name),
            element("td", { className: "px-2 py-1" }, port.port_kind),
            element("td", { className: "px-2 py-1" }, port.active ? "active" : "inactive"),
            element("td", { className: "px-2 py-1 text-xs text-slate-600" }, port.notes || "-")
          )
        );

        if (!port.interfaces || port.interfaces.length === 0) {
          rows.push(
            element(
              "tr",
              { key: "port-empty-" + port.id, className: "bg-slate-50" },
              element("td", { className: "px-2 py-1" }, "Interface"),
              element("td", { className: "px-2 py-1", colSpan: 4 }, "No interfaces")
            )
          );
          return;
        }

        port.interfaces.forEach(function (iface) {
          const ipText = (iface.ips || []).map(function (ipItem) {
            const status = ipItem.active ? "active" : "inactive";
            return ipItem.address + " (" + ipItem.network.name + ", " + status + ")";
          });
          rows.push(
            element(
              "tr",
              { key: "iface-" + iface.id, className: "bg-slate-50" },
              element("td", { className: "px-2 py-1 text-slate-700" }, "Interface"),
              element("td", { className: "px-2 py-1 pl-6" }, iface.identifier),
              element("td", { className: "px-2 py-1" }, iface.mac_address || "-"),
              element("td", { className: "px-2 py-1" }, iface.active ? "active" : "inactive"),
              element("td", { className: "px-2 py-1 text-xs" }, ipText.length ? ipText.join("; ") : "-")
            )
          );
        });
      });

      (assetRow.unassignedInterfaces || []).forEach(function (iface) {
        const ipText = (iface.ips || []).map(function (ipItem) {
          const status = ipItem.active ? "active" : "inactive";
          return ipItem.address + " (" + ipItem.network.name + ", " + status + ")";
        });
        rows.push(
          element(
            "tr",
            { key: "unassigned-" + iface.id, className: "bg-amber-50" },
            element("td", { className: "px-2 py-1 text-amber-800" }, "Interface"),
            element("td", { className: "px-2 py-1" }, "Unassigned / " + iface.identifier),
            element("td", { className: "px-2 py-1" }, iface.mac_address || "-"),
            element("td", { className: "px-2 py-1" }, iface.active ? "active" : "inactive"),
            element("td", { className: "px-2 py-1 text-xs" }, ipText.length ? ipText.join("; ") : "-")
          )
        );
      });

      if (rows.length === 0) {
        rows.push(
          element(
            "tr",
            { key: "empty-all" },
            element("td", { className: "px-2 py-1 text-slate-500", colSpan: 5 }, "No network data")
          )
        );
      }

      return element(
        "table",
        { className: "min-w-full divide-y divide-slate-200 text-xs" },
        element(
          "thead",
          { className: "bg-slate-100" },
          element(
            "tr",
            null,
            ["Type", "Name / Identifier", "MAC / Kind", "State", "IPs"].map(function (label) {
              return element(
                "th",
                { key: label, className: "px-2 py-1 text-left font-medium text-slate-600" },
                label
              );
            })
          )
        ),
        element("tbody", { className: "divide-y divide-slate-200" }, rows)
      );
    }

    function renderAssetView() {
      return element(
        "div",
        null,
        config.canEdit
          ? element(
              "div",
              { className: "mb-4 rounded border border-slate-200 bg-slate-50 p-3" },
              element("p", { className: "mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600" }, "Asset Bulk Paste"),
              element(
                "p",
                { className: "mb-2 text-xs text-slate-500" },
                "Format: id, owner_id, status, os_family_id, os_version_id, group_ids(comma) (TAB-separated)."
              ),
              element("textarea", {
                className: "mb-2 h-24 w-full rounded border border-slate-300 p-2 text-xs",
                value: bulkTextAsset,
                onChange: function (event) {
                  setBulkTextAsset(event.target.value);
                },
                placeholder: "1\t3\tACTIVE\t1\t2\t1,2",
              }),
              element(
                "div",
                { className: "flex items-center gap-2" },
                element(
                  "button",
                  {
                    type: "button",
                    className: "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white",
                    onClick: submitAssetBulkPaste,
                  },
                  "Apply Bulk"
                ),
                bulkInfoAsset ? element("span", { className: "text-xs text-slate-600" }, bulkInfoAsset) : null
              )
            )
          : null,
        element(
          "div",
          { className: "overflow-x-auto" },
          element(
            "table",
            { className: "min-w-full divide-y divide-slate-200 text-sm" },
            element(
              "thead",
              { className: "bg-slate-50" },
              element(
                "tr",
                null,
                ["", "Name", "Owner", "Status", "Groups", "OS Family", "OS Version", ""].map(function (label) {
                  return element(
                    "th",
                    { key: label || "toggle", className: "px-3 py-2 text-left font-medium text-slate-600" },
                    label
                  );
                })
              )
            ),
            element(
              "tbody",
              { className: "divide-y divide-slate-200" },
              assetRows.map(function (row) {
                const rowError = assetErrors[row.id];
                const hasError = !!rowError;
                const familyVersions = versionsByFamily[row.osFamilyId] || [];
                const saving = savingAssetIds.indexOf(row.id) !== -1;
                const isExpanded = !!expandedAssets[row.id];

                return element(
                  React.Fragment,
                  { key: row.id },
                  element(
                    "tr",
                    null,
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "button",
                        {
                          type: "button",
                          className: "rounded border border-slate-300 px-2 py-1 text-xs",
                          onClick: function () {
                            toggleExpandedAsset(row.id);
                          },
                        },
                        isExpanded ? "-" : "+"
                      )
                    ),
                    element("td", { className: "px-3 py-2 font-medium text-slate-900" }, row.name),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError),
                          value: row.ownerId,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleAssetCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            setAssetValue(row.id, "ownerId", event.target.value);
                          },
                        },
                        [element("option", { key: "blank", value: "" }, "Select owner")].concat(
                          renderSelectOptions(lookups.users, "id", function (item) {
                            return item.username;
                          })
                        )
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError),
                          value: row.status,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleAssetCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            setAssetValue(row.id, "status", event.target.value);
                          },
                        },
                        ["ACTIVE", "STORED", "RETIRED", "LOST"].map(function (status) {
                          return element("option", { key: status, value: status }, status);
                        })
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError) + " h-20 min-w-36",
                          multiple: true,
                          value: row.groupIds,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleAssetCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            const selected = Array.from(event.target.selectedOptions).map(function (option) {
                              return option.value;
                            });
                            setAssetGroupValues(row.id, selected);
                          },
                        },
                        renderSelectOptions(lookups.groups, "id", function (item) {
                          return item.name;
                        })
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError),
                          value: row.osFamilyId,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleAssetCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            const familyId = event.target.value;
                            setAssetRows(function (currentRows) {
                              return currentRows.map(function (currentRow) {
                                if (currentRow.id !== row.id) {
                                  return currentRow;
                                }
                                return Object.assign({}, currentRow, {
                                  osFamilyId: familyId,
                                  osVersionId: "",
                                });
                              });
                            });
                          },
                        },
                        [element("option", { key: "empty", value: "" }, "None")].concat(
                          renderSelectOptions(lookups.osFamilies, "id", function (item) {
                            return item.name;
                          })
                        )
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError),
                          value: row.osVersionId,
                          disabled: !config.canEdit || !row.osFamilyId,
                          onKeyDown: function (event) {
                            handleAssetCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            setAssetValue(row.id, "osVersionId", event.target.value);
                          },
                        },
                        [element("option", { key: "empty", value: "" }, "None")].concat(
                          renderSelectOptions(familyVersions, "id", function (item) {
                            return item.version;
                          })
                        )
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "button",
                        {
                          type: "button",
                          className:
                            "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300",
                          disabled: !config.canEdit || saving,
                          onClick: function () {
                            saveAssetRow(row.id);
                          },
                        },
                        saving ? "Saving..." : "Save"
                      )
                    )
                  ),
                  rowError
                    ? element(
                        "tr",
                        { key: "asset-error-" + row.id },
                        element(
                          "td",
                          {
                            colSpan: 8,
                            className: "px-3 py-2 text-xs text-red-700",
                          },
                          rowError
                        )
                      )
                    : null,
                  isExpanded
                    ? element(
                        "tr",
                        { key: "asset-expanded-" + row.id },
                        element(
                          "td",
                          { colSpan: 8, className: "bg-slate-50 px-3 py-3" },
                          renderNetworkHierarchy(row)
                        )
                      )
                    : null
                );
              })
            )
          )
        )
      );
    }

    function renderInterfaceView() {
      return element(
        "div",
        null,
        config.canEdit
          ? element(
              "div",
              { className: "mb-4 rounded border border-slate-200 bg-slate-50 p-3" },
              element("p", { className: "mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600" }, "Interface Bulk Paste"),
              element(
                "p",
                { className: "mb-2 text-xs text-slate-500" },
                "Format: interface_id, port_id, mac, network_id, ip, status, hostname (TAB-separated)."
              ),
              element("textarea", {
                className: "mb-2 h-24 w-full rounded border border-slate-300 p-2 text-xs",
                value: bulkTextInterface,
                onChange: function (event) {
                  setBulkTextInterface(event.target.value);
                },
                placeholder: "7\t12\taa:bb:cc:dd:ee:ff\t1\t10.0.0.15\tSTATIC\tpc-01",
              }),
              element(
                "div",
                { className: "flex items-center gap-2" },
                element(
                  "button",
                  {
                    type: "button",
                    className: "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white",
                    onClick: submitInterfaceBulkPaste,
                  },
                  "Apply Bulk"
                ),
                bulkInfoInterface ? element("span", { className: "text-xs text-slate-600" }, bulkInfoInterface) : null
              )
            )
          : null,
        element(
          "div",
          { className: "overflow-x-auto" },
          element(
            "table",
            { className: "min-w-full divide-y divide-slate-200 text-sm" },
            element(
              "thead",
              { className: "bg-slate-50" },
              element(
                "tr",
                null,
                ["Asset", "Port", "Identifier", "MAC", "Network", "IP", "IP Status", "Hostname", "Active", "IP History", ""].map(function (label) {
                  return element(
                    "th",
                    { key: label, className: "px-3 py-2 text-left font-medium text-slate-600" },
                    label
                  );
                })
              )
            ),
            element(
              "tbody",
              { className: "divide-y divide-slate-200" },
              interfaceRows.map(function (row) {
                const rowError = interfaceErrors[row.id];
                const hasError = !!rowError;
                const saving = savingInterfaceIds.indexOf(row.id) !== -1;
                const assetPorts = portsByAsset[String(row.assetId)] || [];
                const historyText = row.ipHistory
                  .map(function (ipEntry) {
                    const state = ipEntry.active ? "active" : "inactive";
                    return ipEntry.address + " (" + ipEntry.network.name + ", " + state + ")";
                  })
                  .join("; ");

                return element(
                  React.Fragment,
                  { key: row.id },
                  element(
                    "tr",
                    null,
                    element("td", { className: "px-3 py-2 font-medium text-slate-900" }, row.assetName),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError) + " min-w-36",
                          value: row.portId,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleInterfaceCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            setInterfaceValue(row.id, "portId", event.target.value);
                          },
                        },
                        [element("option", { key: "none", value: "" }, "Unassigned")].concat(
                          renderSelectOptions(assetPorts, "id", function (item) {
                            return item.name + " (" + item.port_kind + ")";
                          })
                        )
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element("input", {
                        className: cellClass(hasError) + " min-w-32",
                        value: row.identifier,
                        disabled: !config.canEdit,
                        onKeyDown: function (event) {
                          handleInterfaceCellKeyDown(event, row.id);
                        },
                        onChange: function (event) {
                          setInterfaceValue(row.id, "identifier", event.target.value);
                        },
                      })
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element("input", {
                        className: cellClass(hasError) + " min-w-40",
                        value: row.macAddress,
                        disabled: !config.canEdit,
                        onKeyDown: function (event) {
                          handleInterfaceCellKeyDown(event, row.id);
                        },
                        onChange: function (event) {
                          setInterfaceValue(row.id, "macAddress", event.target.value);
                        },
                        placeholder: "aa:bb:cc:dd:ee:ff",
                      })
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError) + " min-w-40",
                          value: row.networkId,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleInterfaceCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            setInterfaceValue(row.id, "networkId", event.target.value);
                          },
                        },
                        [element("option", { key: "empty", value: "" }, "None")].concat(
                          renderSelectOptions(lookups.networks, "id", function (item) {
                            return item.name + " (" + item.cidr + ")";
                          })
                        )
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element("input", {
                        className: cellClass(hasError) + " min-w-32",
                        value: row.ipAddress,
                        disabled: !config.canEdit,
                        onKeyDown: function (event) {
                          handleInterfaceCellKeyDown(event, row.id);
                        },
                        onChange: function (event) {
                          setInterfaceValue(row.id, "ipAddress", event.target.value);
                        },
                        placeholder: "10.0.0.15",
                      })
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "select",
                        {
                          className: cellClass(hasError),
                          value: row.ipStatus,
                          disabled: !config.canEdit,
                          onKeyDown: function (event) {
                            handleInterfaceCellKeyDown(event, row.id);
                          },
                          onChange: function (event) {
                            setInterfaceValue(row.id, "ipStatus", event.target.value);
                          },
                        },
                        ["STATIC", "DHCP_RESERVED", "DHCP_DYNAMIC", "DEPRECATED"].map(function (status) {
                          return element("option", { key: status, value: status }, status);
                        })
                      )
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element("input", {
                        className: cellClass(hasError) + " min-w-32",
                        value: row.hostname,
                        disabled: !config.canEdit,
                        onKeyDown: function (event) {
                          handleInterfaceCellKeyDown(event, row.id);
                        },
                        onChange: function (event) {
                          setInterfaceValue(row.id, "hostname", event.target.value);
                        },
                      })
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element("input", {
                        type: "checkbox",
                        checked: row.active,
                        disabled: !config.canEdit,
                        onChange: function (event) {
                          setInterfaceValue(row.id, "active", event.target.checked);
                        },
                      })
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2 text-xs text-slate-600" },
                      historyText || "-"
                    ),
                    element(
                      "td",
                      { className: "px-3 py-2" },
                      element(
                        "button",
                        {
                          type: "button",
                          className:
                            "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300",
                          disabled: !config.canEdit || saving,
                          onClick: function () {
                            saveInterfaceRow(row.id);
                          },
                        },
                        saving ? "Saving..." : "Save"
                      )
                    )
                  ),
                  rowError
                    ? element(
                        "tr",
                        { key: "iface-error-" + row.id },
                        element(
                          "td",
                          {
                            colSpan: 11,
                            className: "px-3 py-2 text-xs text-red-700",
                          },
                          rowError
                        )
                      )
                    : null
                );
              })
            )
          )
        )
      );
    }

    if (globalError) {
      return element(
        "div",
        { className: "rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700" },
        globalError
      );
    }

    return element(
      "div",
      null,
      element(
        "div",
        { className: "mb-4 flex items-center gap-2" },
        element(
          "button",
          {
            type: "button",
            className:
              "rounded border px-3 py-1 text-sm " +
              (activeView === "asset"
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-700"),
            onClick: function () {
              setActiveView("asset");
            },
          },
          "Asset View"
        ),
        element(
          "button",
          {
            type: "button",
            className:
              "rounded border px-3 py-1 text-sm " +
              (activeView === "interface"
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-700"),
            onClick: function () {
              setActiveView("interface");
            },
          },
          "Interface View"
        ),
        element(
          "button",
          {
            type: "button",
            className: "ml-auto rounded border border-slate-300 px-3 py-1 text-xs",
            onClick: function () {
              reloadAll().catch(function () {
                setGlobalError("Reload failed.");
              });
            },
          },
          "Reload"
        )
      ),
      activeView === "asset" ? renderAssetView() : renderInterfaceView()
    );
  }

  ReactDOM.createRoot(mountNode).render(element(OverviewApp));
})();
