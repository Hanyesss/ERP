import type { CSSProperties } from "react";
import { Select } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getCounterparties } from "../../api/counterparties";

interface Props {
  type: "client" | "supplier";
  value?: string;
  onChange?: (value: string | undefined) => void;
  placeholder?: string;
  size?: "small" | "middle" | "large";
  allowClear?: boolean;
  style?: CSSProperties;
  disabled?: boolean;
}

export default function CounterpartySelect({ type, ...rest }: Props) {
  const queryKey = type === "client" ? "counterparties-clients" : "counterparties-suppliers";

  const { data, isLoading } = useQuery({
    queryKey: [queryKey],
    queryFn: () => getCounterparties({ type, page_size: 200 }).then(r => r.data),
  });

  const options = (data?.items || []).map(c => ({
    value: c.id,
    label: c.name_cn ? `${c.name} / ${c.name_cn}` : c.name,
  }));

  return (
    <Select
      showSearch
      loading={isLoading}
      options={options}
      filterOption={(input, option) =>
        (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
      }
      {...rest}
    />
  );
}
